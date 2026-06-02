import os
import threading
import customtkinter as ctk
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from testing import LOG_FILE, run_test

# --- GUI Setup ---
ctk.set_appearance_mode("System")
app = ctk.CTk()
app.title("Internet Speed Tracker")
app.geometry("1600x600")

# Global variables for state management
scheduler_job = None
test_is_running = False
current_time_frame = "Past Day"

show_min_lines = True
show_raw_lines = True
show_smoothed_lines = False

SLIDER_OPTIONS = ["Manual", "0 mins (Continuous)", "5 mins", "10 mins", "15 mins", "30 mins", "1 hr"]
SLIDER_VALUES = [-1, 0, 5, 10, 15, 30, 60]

# --- Core Logic Functions ---

def change_time_frame(value):
    """Callback triggered whenever the timeline selector filter changes."""
    global current_time_frame
    current_time_frame = value
    load_graph_data()

def get_target_thresholds():
    """Unified entry parsing to pull minimum thresholds from UI inputs safely."""
    try:
        dl_text = download_min_entry.get().strip()
        ul_text = upload_min_entry.get().strip()
        return (float(dl_text) if dl_text else 0.0, 
                float(ul_text) if ul_text else 0.0)
    except ValueError:
        return 0.0, 0.0

def load_graph_data():
    """Reads CSV data and updates speed and ping matplotlib charts."""
    ax_speed.clear()
    ax_ping.clear()
    
    # Reset face colors after clear operations
    ax_speed.set_facecolor('#1e1e1e')
    ax_ping.set_facecolor('#1e1e1e')

    if not os.path.exists(LOG_FILE):
        show_empty_chart_message("No log file detected yet.")
        return

    try:
        df = pd.read_csv(LOG_FILE)
        if df.empty:
            show_empty_chart_message("Log dataset file is empty.")
            return
        
        # 1. Chronological DateTime Conversion
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
        
        # 2. Time-window segmentation filtering
        now = pd.Timestamp.now()
        if current_time_frame == "Past Hour":
            cutoff = now - pd.Timedelta(hours=1)
            df = df[df['Timestamp'] >= cutoff]
            date_format = '%H:%M:%S'
        elif current_time_frame == "Past Day":
            cutoff = now - pd.Timedelta(days=1)
            df = df[df['Timestamp'] >= cutoff]
            date_format = '%H:%M'
        elif current_time_frame == "Past Week":
            cutoff = now - pd.Timedelta(weeks=1)
            df = df[df['Timestamp'] >= cutoff]
            date_format = '%b %d %H:%M'
        elif current_time_frame == "Past Month":
            cutoff = now - pd.Timedelta(days=30)
            df = df[df['Timestamp'] >= cutoff]
            date_format = '%b %d'
        else:
            date_format = '%b %d %H:%M'

        if df.empty:
            show_empty_chart_message(f"No data recorded in the {current_time_frame}")
            return
        
        # Sort values chronologically to prevent line graphing glitches
        df = df.sort_values('Timestamp')

        # 3. Handle Rolling Trend Math Data Mapping
        if show_smoothed_lines:
            df['DL_Smooth'] = df['Download Speed (Mbps)'].rolling(window=5, min_periods=1).mean()
            df['UL_Smooth'] = df['Upload Speed (Mbps)'].rolling(window=5, min_periods=1).mean()
            df['Ping_Smooth'] = df['Ping (ms)'].rolling(window=5, min_periods=1).mean()

        # 4. RENDER TOP CHART: Bandwidth Speeds (ax_speed)
        if show_raw_lines:
            ax_speed.plot(df['Timestamp'], df['Download Speed (Mbps)'], label='Download (Raw)', color='#1f77b4', linewidth=1.2, alpha=0.8)
            ax_speed.plot(df['Timestamp'], df['Upload Speed (Mbps)'], label='Upload (Raw)', color='#2ca02c', linewidth=1.2, alpha=0.8)

        if show_smoothed_lines:
            ax_speed.plot(df['Timestamp'], df['DL_Smooth'], label='Download (Smoothed)', color='#6baed6', linewidth=2.2)
            ax_speed.plot(df['Timestamp'], df['UL_Smooth'], label='Upload (Smoothed)', color='#74c476', linewidth=2.2)

        if show_min_lines:
            dl_min, ul_min = get_target_thresholds()

            if dl_min > 0:
                ax_speed.axhline(y=dl_min, color='#1f77b4', linestyle='--', alpha=0.6, label='Min Download')
                ax_speed.fill_between(df['Timestamp'], 0, dl_min, color='red', alpha=0.03)
            if ul_min > 0:
                ax_speed.axhline(y=ul_min, color='#2ca02c', linestyle='--', alpha=0.6, label='Min Upload')
        
        ax_speed.set_title(f"Network Performance History ({current_time_frame})", color="white", pad=10)
        ax_speed.set_ylabel("Mbps", color="white")
        ax_speed.grid(True, linestyle=':', alpha=0.2)
        ax_speed.legend(loc="upper left", framealpha=0.2, facecolor="black", edgecolor="none", labelcolor="white", fontsize='x-small')
        ax_speed.tick_params(colors='white', axis='y')

        # 5. RENDER BOTTOM CHART: Latency/Ping (ax_ping)
        if show_raw_lines:
            ax_ping.plot(df['Timestamp'], df['Ping (ms)'], label='Ping (Raw)', color='#d62728', linewidth=1.2, alpha=0.8)
            
        if show_smoothed_lines:
            ax_ping.plot(df['Timestamp'], df['Ping_Smooth'], label='Ping (Smoothed)', color='#ff9896', linewidth=2.2)
            
        ax_ping.set_ylabel("Ping (ms)", color="white")
        ax_ping.grid(True, linestyle=':', alpha=0.2)
        ax_ping.legend(loc="upper left", framealpha=0.2, facecolor="black", edgecolor="none", labelcolor="white", fontsize='x-small')
        
        # 6. Synchronized Timeline X-Axis Formatting
        ax_ping.xaxis.set_major_formatter(mdates.DateFormatter(date_format))
        ax_ping.tick_params(colors='white', axis='x', rotation=25)
        ax_ping.tick_params(colors='white', axis='y')
        
        fig.tight_layout()
        canvas.draw()
    except Exception as e:
        print(f"Error updating graph: {e}")

def show_empty_chart_message(message):
    """Safely renders clear status updates to empty layout frames."""
    ax_speed.text(0.5, 0.5, message, color="white", ha="center", va="center", transform=ax_speed.transAxes)
    ax_ping.text(0.5, 0.5, "No metrics available.", color="gray", ha="center", va="center", transform=ax_ping.transAxes)
    canvas.draw()

def async_test_execution():
    """Runs the speed test on a background thread to prevent UI freezing."""
    global test_is_running
    
    if test_is_running:
        return
        
    test_is_running = True
    status_label.configure(text="Status: Running speed test... Please wait.", text_color="yellow")
    test_button.configure(state="disabled")

    dl_min, ul_min = get_target_thresholds()

    def thread_target():
        try:
            status, data = run_test(download_min=dl_min, upload_min=ul_min)
            app.after(0, lambda: update_ui_elements(status, data))
        except Exception as e:
            print(f"Error during background test execution: {e}")
            app.after(0, reset_test_lock) 

    threading.Thread(target=thread_target, daemon=True).start()

def update_ui_elements(status, data):
    """Updates GUI summary metrics and refreshes the trends graph."""
    global test_is_running
    
    test_button.configure(state="normal")
    
    if status == "PASS":
        status_label.configure(text="Status: PASS", text_color="green")
    else:
        status_label.configure(text="Status: FAIL", text_color="red")

    summary_text = (
        f"Latest Test Metrics:\n"
        f"─────────────────────────────\n"
        f"ISP: {data.get('isp', 'Unknown')}\n"
        f"Server: {data.get('server_name', 'Unknown')} ({data.get('server_location', 'Unknown')})\n"
        f"Download: {data.get('download', 0.0):.2f} Mbps\n"
        f"Upload: {data.get('upload', 0.0):.2f} Mbps\n"
        f"Ping: {data.get('ping', 0.0):.1f} ms"
    )
    info_panel.configure(text=summary_text)
    
    load_graph_data()
    test_is_running = False

def reset_test_lock():
    """Fallback to unlock the UI if something breaks."""
    global test_is_running
    test_is_running = False
    test_button.configure(state="normal")
    status_label.configure(text="Status: Error occurred.", text_color="orange")

def handle_schedule_update(value):
    """Maps uniform slider steps to explicit timing intervals."""
    global scheduler_job
    
    idx = int(value)
    slider_label.configure(text=f"Interval: {SLIDER_OPTIONS[idx]}")
    
    if scheduler_job:
        app.after_cancel(scheduler_job)
        scheduler_job = None
        
    minutes = SLIDER_VALUES[idx]
    if minutes >= 0:
        manage_loop(minutes)

def manage_loop(minutes):
    """Recursive callback that runs or queues the next test loop."""
    global scheduler_job

    if not test_is_running:
        async_test_execution()
    
    ms_delay = 1000 if minutes == 0 else minutes * 60000
    scheduler_job = app.after(ms_delay, lambda: manage_loop(minutes))

def toggle_min_lines():
    global show_min_lines
    show_min_lines = min_lines_check.get()
    load_graph_data()

def toggle_raw_lines():
    global show_raw_lines
    show_raw_lines = raw_lines_check.get()
    load_graph_data()

def toggle_smoothed_lines():
    global show_smoothed_lines
    show_smoothed_lines = smoothed_lines_check.get()
    load_graph_data()

# --- UI Layout Design Structure ---

control_frame = ctk.CTkFrame(app, width=300)
control_frame.pack(side="left", fill="y", padx=15, pady=15)

test_button = ctk.CTkButton(control_frame, text="Run Speed Test", command=async_test_execution)
test_button.pack(pady=15, padx=10, fill="x")

download_min_entry = ctk.CTkEntry(control_frame, placeholder_text="Min Download Speed (Default: 0 Mbps)")
download_min_entry.pack(pady=10, padx=10, fill="x")
download_min_entry.bind("<KeyRelease>", lambda event: load_graph_data())

upload_min_entry = ctk.CTkEntry(control_frame, placeholder_text="Min Upload Speed (Default: 0 Mbps)")
upload_min_entry.pack(pady=10, padx=10, fill="x")
upload_min_entry.bind("<KeyRelease>", lambda event: load_graph_data())

checkbox_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
checkbox_frame.pack(pady=10, padx=10, fill="x")

raw_lines_check = ctk.CTkCheckBox(checkbox_frame, text="Show Raw Data", command=toggle_raw_lines)
raw_lines_check.select()
raw_lines_check.pack(anchor="w", pady=5)

smoothed_lines_check = ctk.CTkCheckBox(checkbox_frame, text="Show Smoothed Trend", command=toggle_smoothed_lines)
smoothed_lines_check.deselect()
smoothed_lines_check.pack(anchor="w", pady=5)

min_lines_check = ctk.CTkCheckBox(checkbox_frame, text="Show Target Thresholds", command=toggle_min_lines)
min_lines_check.select()
min_lines_check.pack(anchor="w", pady=5)

slider_label = ctk.CTkLabel(control_frame, text="Interval: Manual")
slider_label.pack(pady=(15, 0))

interval_slider = ctk.CTkSlider(
    control_frame, 
    from_=0, 
    to=6, 
    number_of_steps=6, 
    command=handle_schedule_update
)
interval_slider.set(0)
interval_slider.pack(pady=10, padx=10, fill="x")

status_label = ctk.CTkLabel(control_frame, text="Status: Idle", font=("Arial", 13, "bold"))
status_label.pack(pady=15)

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

display_frame = ctk.CTkFrame(app)
display_frame.pack(side="right", fill="both", expand=True, padx=15, pady=15)

time_frame_switch = ctk.CTkSegmentedButton(
    display_frame, 
    values=["Past Hour", "Past Day", "Past Week", "Past Month", "All History"],
    command=change_time_frame
)
time_frame_switch.set("Past Day")
time_frame_switch.pack(pady=(10, 5), padx=10, fill="x")

fig, (ax_speed, ax_ping) = plt.subplots(nrows=2, ncols=1, figsize=(5, 6), dpi=100, sharex=True)
fig.patch.set_facecolor('#1e1e1e') 

canvas = FigureCanvasTkAgg(fig, master=display_frame)
canvas.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)

load_graph_data()
app.mainloop()