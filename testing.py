import csv
import os
from datetime import datetime
from dotenv import load_dotenv
import requests
import speedtest

# Initialize environment configuration parsing
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

LOG_FILE = 'speed_tracker_log.csv'
STATUS_FILE = 'last_known_state.txt'

CSV_HEADERS = [
    'Timestamp', 
    'Test Type',
    'ISP',
    'Server Name',
    'Server Location',
    'Download Speed (Mbps)', 
    'Upload Speed (Mbps)', 
    'Ping (ms)',
    'Status'
]

ERROR_FALLBACK_DATA = {
    'download': 0.0, 'upload': 0.0, 'ping': -1.0, 'isp': 'N/A',
    'server_name': 'N/A', 'server_location': 'N/A', 'server_id': None
}

def calculate_status(data, download_min, upload_min):
    """Unified logic to determine if test metrics meet or exceed the minimum thresholds."""
    is_good_download = data.get('download', 0.0) >= download_min
    is_good_upload = data.get('upload', 0.0) >= upload_min
    return "PASS" if (is_good_download and is_good_upload) else "FAIL"

def get_previous_state():
    """Reads the last recorded operational state from local disk."""
    if not os.path.exists(STATUS_FILE):
        return "UNKNOWN"
    with open(STATUS_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()

def save_current_state(status):
    """Saves the current operational state onto the disk profile layer."""
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        f.write(status)

def send_telegram_notification(message):
    """Dispatches a payload string out to the configured Telegram endpoint."""
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ Warning: Notification requested but Telegram credentials are missing.")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        # 8-second safety timeout so your UI frame doesn't lock up if offline
        requests.post(url, json=payload, timeout=8)
    except Exception as e:
        print(f"Failed to dispatch network alert payload: {e}")

def check_speed(st_instance, failed_server_id=None):
    """Runs speed test routines using an explicitly provided Speedtest instance."""
    print("Retrieving server list...")
    try:
        all_servers = st_instance.get_servers()
    except Exception as e:
        print(f"⚠️ Error retrieving server list: {e}. Attempting automated fallback selection.")
        all_servers = {}

    if failed_server_id and all_servers:
        print(f"🔄 Selecting a different fallback server (excluding ID: {failed_server_id})...")
        flattened_servers = [server for server_list in all_servers.values() for server in server_list]
        fallback_server = next((s for s in flattened_servers if s['id'] != failed_server_id), None)
        
        if fallback_server:
            st_instance.results.server = fallback_server
            print(f"Targeting fallback server: {fallback_server.get('sponsor')} ({fallback_server.get('name')})")
        else:
            print("⚠️ Could not find a distinct fallback server. Defaulting to best choice.")
            st_instance.get_best_server()
    else:
        print("Testing internet speed on best automatic server...")
        st_instance.get_best_server()

    print("Testing download speed...")
    download_speed = st_instance.download(threads=8) / 1_000_000  # Convert to Mbps
    
    print("Testing upload speed...")
    upload_speed = st_instance.upload(threads=8) / 1_000_000      # Convert to Mbps

    results = st_instance.results
    isp = st_instance.config.get('client', {}).get('isp', 'Unknown ISP')
    server_location = f"{results.server.get('name', '')}, {results.server.get('country', '')}"

    return {
        'download': download_speed,
        'upload': upload_speed,
        'ping': results.ping,
        'isp': isp,
        'server_name': results.server.get('sponsor', 'Unknown Server'),
        'server_location': server_location,
        'server_id': results.server.get('id')
    }

def process_and_log_results(test_type, data, download_min, upload_min):
    """Evaluates final cycle metrics against constraints, manages notifications, and logs."""
    # Use the helper function here
    status = calculate_status(data, download_min, upload_min)

    print(f"\n--- {test_type.upper()} FINAL VERDICT ---")
    print(f"Status:          {status}\n")

    prev_status = get_previous_state()

    if status == "FAIL" and prev_status != "FAIL":
        alert_msg = (
            f"🚨 *Network Performance Dropped below Target Threshold!*\n\n"
            f"• *Download:* {data['download']:.2f} Mbps\n"
            f"• *Upload:* {data['upload']:.2f} Mbps\n"
            f"• *Ping:* {data['ping']:.1f} ms\n"
            f"• *Target Server:* {data['server_name']}"
        )
        send_telegram_notification(alert_msg)

    elif status == "PASS" and prev_status == "FAIL":
        recovery_msg = (
            f"✅ *Network Performance Restored to Normal Baseline*\n\n"
            f"• *Download:* {data['download']:.2f} Mbps\n"
            f"• *Upload:* {data['upload']:.2f} Mbps\n"
            f"• *Ping:* {data['ping']:.1f} ms\n"
            f"• *Target Server:* {data['server_name']}"
        )
        send_telegram_notification(recovery_msg)

    save_current_state(status)
    _log_to_csv(test_type, data, status)
    return status

def run_test(download_min=0.0, upload_min=0.0):
    """Executes speedtest sequences cleanly, suppressing transient blips."""
    try:
        st_instance = speedtest.Speedtest(secure=True)
    except Exception as e:
        print(f"Failed to initialize speedtest library: {e}")
        return "FAIL", ERROR_FALLBACK_DATA

    # --- FIRST ATTEMPT ---
    try:
        print("Running initial speed test...")
        initial_data = check_speed(st_instance)
        # Use the helper function here
        initial_status = calculate_status(initial_data, download_min, upload_min)
    except Exception as e:
        print(f"Error on initial pass execution: {e}")
        initial_status = "FAIL"
        initial_data = ERROR_FALLBACK_DATA

    # If the initial test passes, log it and wrap up immediately
    if initial_status == "PASS":
        final_status = process_and_log_results('Initial', initial_data, download_min, upload_min)
        return final_status, initial_data

    # --- RETRY ATTEMPT ---
    print("🔄 First test FAILED. Verifying with fallback test before alerting...")
    try:
        fallback_data = check_speed(st_instance, failed_server_id=initial_data.get('server_id'))
        
        # Log the initial failure silently to CSV for data consistency on your graphs
        _log_to_csv('Initial', initial_data, "FAIL")
        
        # Process the fallback results to handle notifications and finalize status
        final_status = process_and_log_results('Fallback', fallback_data, download_min, upload_min)
        return final_status, fallback_data

    except Exception as e:
        print(f"Error on fallback execution attempt: {e}")
        final_status = process_and_log_results('Initial', initial_data, download_min, upload_min)
        return final_status, initial_data
    
def _log_to_csv(test_type, data, status):
    """Internal helper to write test metrics to the CSV file."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    file_exists = os.path.exists(LOG_FILE)
    with open(LOG_FILE, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(CSV_HEADERS)
        writer.writerow([
            timestamp, test_type, data['isp'], data['server_name'], data['server_location'],
            round(data['download'], 2), round(data['upload'], 2), round(data['ping'], 1), status
        ])