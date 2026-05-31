from testing import run_test, LOG_FILE
import customtkinter as ctk
import threading
import pandas as pd
import os
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# --- GUI Setup ---
ctk.set_appearance_mode("System")
app = ctk.CTk()
app.title("Internet Speed Tracker")
app.geometry("800x600") # Expanded geometry to accommodate graphs and data

# Global reference for the auto-scheduler loop
scheduler_job = None
test_is_running = False

# The display names for the slider intervals
SLIDER_OPTIONS = ["Manual", "0 mins (Continuous)", "5 mins", "10 mins", "15 mins", "30 mins", "1 hr"]

# The actual minute values used by the scheduler loop (-1 represents Manual)
SLIDER_VALUES = [-1, 0, 5, 10, 15, 30, 60]

# --- Core Logic Functions ---

def load_graph_data():
    """Reads CSV data and updates the matplotlib chart trendlines."""
    if not os.path.exists(LOG_FILE):
        return

    # Clear previous plot
    ax.clear()
    
    try:
        df = pd.read_csv(LOG_FILE)
        if df.empty: return
        
        # Take up to the last 10 entries to keep the graph readable
        df = df.tail(10)
        
        # Plot Download and Upload trends
        ax.plot(df['Timestamp'], df['Download Speed (Mbps)'], marker='o', label='Download', color='#1f77b4')
        ax.plot(df['Timestamp'], df['Upload Speed (Mbps)'], marker='o', label='Upload', color='#2ca02c')
        
        ax.set_title("Speed History (Last 10 Tests)", color="white")
        ax.tick_params(colors='white', axis='x', rotation=20)
        ax.tick_params(colors='white', axis='y')
        ax.set_ylabel("Mbps", color="white")
        ax.legend()
        ax.grid(True, linestyle='--', alpha=0.3)
        fig.tight_layout()
        
        canvas.draw()
    except Exception as e:
        print(f"Error updating graph: {e}")

def async_test_execution():
    """Runs the speed test on a background thread to prevent UI freezing."""
    global test_is_running
    
    # SAFETY CHECK: If a test is already running, do nothing!
    if test_is_running:
        print("⚠️ Test requested, but a test is already in progress. Skipping.")
        return
        
    # Set the lock
    test_is_running = True
    status_label.configure(text="Status: Running speed test... Please wait.", text_color="yellow")
    test_button.configure(state="disabled")

    try:
        dl_min = float(download_min_entry.get()) if download_min_entry.get() else 250.0
        ul_min = float(upload_min_entry.get()) if upload_min_entry.get() else 0.0
    except ValueError:
        dl_min, ul_min = 250.0, 0.0

    def thread_target():
        try:
            status, data = run_test(download_min=dl_min, upload_min=ul_min)
            app.after(0, lambda: update_ui_elements(status, data))
        except Exception as e:
            print(f"Error during background test: {e}")
            # Release lock even if it crashes
            app.after(0, lambda: reset_test_lock()) 

    threading.Thread(target=thread_target, daemon=True).start()

def update_ui_elements(status, data):
    """Updates GUI summary metrics and refreshes the trends graph."""
    global test_is_running
    
    test_button.configure(state="normal")
    
    if status == "PASS":
        status_label.configure(text=f"Status: PASS", text_color="green")
    else:
        status_label.configure(text=f"Status: FAIL", text_color="red")

    summary_text = (
        f"Latest Test Metrics:\n"
        f"─────────────────────────────\n"
        f"ISP: {data['isp']}\n"
        f"Server: {data['server_name']} ({data['server_location']})\n"
        f"Download: {data['download']:.2f} Mbps\n"
        f"Upload: {data['upload']:.2f} Mbps\n"
        f"Ping: {data['ping']:.1f} ms"
    )
    info_panel.configure(text=summary_text)
    
    load_graph_data()
    
    # Release the lock!
    test_is_running = False

def reset_test_lock():
    """Fallback to unlock the UI if something breaks."""
    global test_is_running
    test_is_running = False
    test_button.configure(state="normal")
    status_label.configure(text="Status: Error occurred.", text_color="orange")

def handle_schedule_update(value):
    """Maps the uniform slider index to non-uniform custom time steps."""
    global scheduler_job
    
    # Convert slider float value to an integer index (0 to 6)
    idx = int(value)
    
    # Update the slider label text dynamically
    slider_label.configure(text=f"Interval: {SLIDER_OPTIONS[idx]}")
    
    # Cancel any active schedules before setting a new one
    if scheduler_job:
        app.after_cancel(scheduler_job)
        scheduler_job = None
        
    minutes = SLIDER_VALUES[idx]
    
    if minutes == 0:
        # Continuous mode: Start checking immediately
        manage_loop(0)
    elif minutes > 0:
        # Standard timed interval mode
        manage_loop(minutes)
    else:
        # Manual mode (-1) does nothing, leaving it idle
        pass

def manage_loop(minutes):
    """Recursive callback that runs or queues the next test."""
    global scheduler_job
    
    if minutes == 0:
        # Continuous Mode logic
        if not test_is_running:
            async_test_execution()
        # Check again in 1 second to see if the test finished or is still busy
        scheduler_job = app.after(1000, lambda: manage_loop(0))
    else:
        # Standard Interval logic
        if not test_is_running:
            async_test_execution()
        # Schedule the next test checkpoint in X minutes
        scheduler_job = app.after(minutes * 60000, lambda: manage_loop(minutes))


# --- UI Layout Design Structure ---

# Left Side Panel - Configurations & Status
control_frame = ctk.CTkFrame(app, width=300)
control_frame.pack(side="left", fill="y", padx=15, pady=15)

test_button = ctk.CTkButton(control_frame, text="Run Speed Test", command=async_test_execution)
test_button.pack(pady=15, padx=10, fill="x")

download_min_entry = ctk.CTkEntry(control_frame, placeholder_text="Min Download Speed (Mbps)")
download_min_entry.pack(pady=10, padx=10, fill="x")

upload_min_entry = ctk.CTkEntry(control_frame, placeholder_text="Min Upload Speed (Mbps)")
upload_min_entry.pack(pady=10, padx=10, fill="x")

# Slider interface for time variables
slider_label = ctk.CTkLabel(control_frame, text="Interval: Manual")
slider_label.pack(pady=(15, 0))

# We use from_=0 to to_=6 because we have 7 unique steps in our lists
interval_slider = ctk.CTkSlider(
    control_frame, 
    from_=0, 
    to=6, 
    number_of_steps=6, 
    command=handle_schedule_update
)
interval_slider.set(0) # Start turned off on "Manual"
interval_slider.pack(pady=10, padx=10, fill="x")

status_label = ctk.CTkLabel(control_frame, text="Status: Idle", font=("Arial", 13, "bold"))
status_label.pack(pady=15)

# Big information callout box from most previous test
info_panel = ctk.CTkLabel(
    control_frame, 
    text="No recent test data.\nClick 'Run Speed Test' to begin.", 
    justify="left", 
    anchor="w",
    fg_color="#2b2b2b",
    corner_radius=6,
    padx=10,
    pady=10
)
info_panel.pack(pady=10, padx=10, fill="both", expand=True)


# Right Side Panel - Visual Graphs over time
display_frame = ctk.CTkFrame(app)
display_frame.pack(side="right", fill="both", expand=True, padx=15, pady=15)

# Matplotlib Figure integration setup
fig, ax = plt.subplots(figsize=(5, 4), dpi=100)
fig.patch.set_facecolor('#1e1e1e') # Dark mode theme matching CustomTkinter standard color
ax.set_facecolor('#1e1e1e')

canvas = FigureCanvasTkAgg(fig, master=display_frame)
canvas.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)

# Initial graph display pull sequence when UI opens
load_graph_data()

app.mainloop()