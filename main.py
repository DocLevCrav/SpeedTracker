import speedtest

st = speedtest.Speedtest()
downloadMin = 10 # Minimum download speed in Mbps
uploadMin = 10 # Minimum upload speed in Mbps

def checkSpeed():
    st.get_best_server()
    downloadSpeed = st.download() / 1000000  # Convert to Mbps
    uploadSpeed = st.upload() / 1000000  # Convert to Mbps
    return downloadSpeed, uploadSpeed

def main():
    downloadSpeed, uploadSpeed = checkSpeed()
    print(f"Download Speed: {downloadSpeed:.2f} Mbps")
    print(f"Upload Speed: {uploadSpeed:.2f} Mbps")

    if downloadSpeed < downloadMin:
        print("Download speed is below the minimum threshold.")
    else:
        print("Download speed is above the minimum threshold.")

    if uploadSpeed < uploadMin:
        print("Upload speed is below the minimum threshold.")
    else:
        print("Upload speed is above the minimum threshold.")

if __name__ == "__main__":
    main()