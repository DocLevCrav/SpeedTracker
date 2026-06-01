import speedtest
import csv
import os
from datetime import datetime

st = speedtest.Speedtest(secure=True)
DOWNLOAD_MIN = 0 # Default fallback minimum download speed in Mbps
UPLOAD_MIN = 0   # Default fallback minimum upload speed in Mbps
LOG_FILE = 'speed_tracker_log.csv'

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

"""
Runs the speed test. Picks the best server by default, but if a failed_server_id is provided, it will attempt to select a different server for testing.
If failed_server_id is passed, it manually selects a different fallback server.
"""
def check_speed(failed_server_id=None):
    print("Retrieving server list...")
    all_servers = st.get_servers()

    if failed_server_id:
        print(f"🔄 Selecting a different fallback server (excluding ID: {failed_server_id})...")
        
        # Flatten the nested server dictionary into a single list of servers
        flattened_servers = [server for server_list in all_servers.values() for server in server_list]
        
        # Find the first server that doesn't match our failed server ID
        fallback_server = next((s for s in flattened_servers if s['id'] != failed_server_id), None)
        
        if fallback_server:
            # Assign the server manually to avoid the speedtest-cli library type bug
            st.results.server = fallback_server
            print(f"Targeting fallback server: {fallback_server.get('sponsor')} ({fallback_server.get('name')})")
        else:
            print("⚠️ Could not find a distinct fallback server. Defaulting to best automatic choice.")
            st.get_best_server()
    else:
        print("Testing internet speed on best automatic server...")
        st.get_best_server()

    print("Testing download speed...")
    # Force the library to use 8 parallel threads to calculate download accurately
    downloadSpeed = st.download(threads=8) / 1_000_000  # Convert to Mbps
    
    print("Testing upload speed...")
    # Force the library to use 8 parallel threads for upload consistency
    uploadSpeed = st.upload(threads=8) / 1_000_000      # Convert to Mbps

    results = st.results
    isp = st.config.get('client', {}).get('isp', 'Unknown ISP')
    server_location = f"{results.server.get('name', '')}, {results.server.get('country', '')}"

    return {
        'download': downloadSpeed,
        'upload': uploadSpeed,
        'ping': results.ping,
        'isp': isp,
        'server_name': results.server.get('sponsor', 'Unknown Server'),
        'server_location': server_location,
        'server_id': results.server.get('id')
    }

"""
Processes the speed test results, prints a formatted summary to the console, and logs the results to a CSV file. 
It evaluates whether the download and upload speeds meet the defined minimum thresholds and assigns a PASS/FAIL status accordingly.
"""
def process_and_log_results(test_type, data):
    """Evaluates data, prints formatted output, and saves to CSV."""
    is_good_download = data['download'] >= DOWNLOAD_MIN
    is_good_upload = data['upload'] >= UPLOAD_MIN
    status = "PASS" if (is_good_download and is_good_upload) else "FAIL"
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    print(f"\n--- {test_type.upper()} TEST RESULTS ---")
    print(f"Timestamp:       {timestamp}")
    print(f"ISP:             {data['isp']}")
    print(f"Server:          {data['server_name']} ({data['server_location']})")
    print(f"Download Speed:  {data['download']:.2f} Mbps " + ("✅" if is_good_download else "❌ (Below Min)"))
    print(f"Upload Speed:    {data['upload']:.2f} Mbps " + ("✅" if is_good_upload else "❌ (Below Min)"))
    print(f"Ping:            {data['ping']:.1f} ms")
    print(f"Status:          {status}\n")

    # Log to CSV
    file_exists = os.path.exists(LOG_FILE)
    with open(LOG_FILE, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(CSV_HEADERS)
        writer.writerow([
            timestamp, test_type, data['isp'], data['server_name'], data['server_location'],
            round(data['download'], 2), round(data['upload'], 2), round(data['ping'], 1), status
        ])
        
    return status


def run_test(download_min, upload_min):
    global DOWNLOAD_MIN, UPLOAD_MIN
    DOWNLOAD_MIN = download_min
    UPLOAD_MIN = upload_min
    # --- FIRST ATTEMPT ---
    result_data = check_speed()
    status = process_and_log_results('Initial', result_data)

    # --- RETRY ATTEMPT ---
    if status == "FAIL":
        print(f"🔄 First test FAILED. Running fallback test...")
        fallback_data = check_speed(failed_server_id=result_data['server_id'])
        process_and_log_results('Fallback', fallback_data)
        return status, fallback_data
    
    return status, result_data