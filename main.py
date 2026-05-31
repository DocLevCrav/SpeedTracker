import speedtest
import csv
import os
from datetime import datetime

st = speedtest.Speedtest()
downloadMin = 10 # Minimum download speed in Mbps
uploadMin = 10 # Minimum upload speed in Mbps
LOG_FILE = 'speed_tracker_log.csv'

csvHeaders = [
    'Timestamp', 
    'ISP',
    'Server Name',
    'Server Location',
    'Download Speed (Mbps)', 
    'Upload Speed (Mbps)', 
    'Ping (ms)',
    'Status'
]

def checkSpeed():
    print("Testing internet speed...")
    st.get_best_server()

    downloadSpeed = st.download() / 1000000  # Convert to Mbps
    uploadSpeed = st.upload() / 1000000  # Convert to Mbps
    ping = st.results.ping

    config = st.config.get('client', {})
    isp = config.get('isp', 'Unknown ISP')

    best_server = st.results.server
    server_name = best_server.get('sponsor', 'Unknown Server')
    server_location = f"{best_server.get('name', '')}, {best_server.get('country', '')}"

    return downloadSpeed, uploadSpeed, ping, isp, server_name, server_location

def logToCsv(data_row):
    # Check if file exists before opening it to determine if headers are needed
    file_exists = os.path.exists(LOG_FILE)
    
    # Open in append mode ('a') with newline='' to prevent blank lines on Windows
    with open(LOG_FILE, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        
        # If it's a brand-new file, write the header row first
        if not file_exists:
            writer.writerow(csvHeaders)
            
        writer.writerow(data_row)
    print(f"Successfully logged results to {LOG_FILE}")

def main():
    downloadSpeed, uploadSpeed, ping, isp, server_name, server_location = checkSpeed()

    is_good_download = downloadSpeed >= downloadMin
    is_good_upload = uploadSpeed >= uploadMin
    status = "PASS" if (is_good_download and is_good_upload) else "FAIL"

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    print("\n--- TEST RESULTS ---")
    print(f"Timestamp:       {timestamp}")
    print(f"ISP:             {isp}")
    print(f"Server:          {server_name} ({server_location})")
    print(f"Download Speed:  {downloadSpeed:.2f} Mbps " + ("✅" if is_good_download else "❌ (Below Min)"))
    print(f"Upload Speed:    {uploadSpeed:.2f} Mbps " + ("✅" if is_good_upload else "❌ (Below Min)"))
    print(f"Ping:            {ping:.1f} ms\n")
    print(f"Status:          {status}\n")

    data_row = [
        timestamp,
        isp,
        server_name,
        server_location,
        round(downloadSpeed, 2),
        round(uploadSpeed, 2),
        round(ping, 1),
        status
    ]

    logToCsv(data_row)

if __name__ == "__main__":
    main()