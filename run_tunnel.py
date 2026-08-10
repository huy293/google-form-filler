import subprocess
import re
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')

# Run localhost.run reverse tunnel
cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ServerAliveInterval=30", "-R", "80:localhost:8080", "nokey@localhost.run"]

print("Starting localhost.run tunnel subprocess...")
process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')

url_found = False
start_time = time.time()

# Let's read for up to 30 seconds
while time.time() - start_time < 30:
    line = process.stdout.readline()
    if not line:
        if process.poll() is not None:
            print("Process terminated early with code:", process.poll())
            break
        time.sleep(0.5)
        continue
        
    print(f"Tunnel: {line.strip()}")
    
    # Check for localhost.run or lhr.life URL
    match = re.search(r'https?://[a-zA-Z0-9.-]+\.(?:localhost\.run|lhr\.life)', line)
    if match:
        url = match.group(0)
        # Skip static marketing URLs in welcome banner
        if "admin.localhost.run" in url or "www.localhost.run" in url:
            continue
            
        # Ensure it is https
        if url.startswith("http://"):
            url = url.replace("http://", "https://")
        print(f"\n==================================================")
        print(f"SUCCESS: Tunnel URL found -> {url}")
        print(f"==================================================\n")
        with open("tunnel_url.txt", "w") as f:
            f.write(url)
        url_found = True
        break

if url_found:
    print("Keeping tunnel alive... Press Ctrl+C in terminal to stop.")
    try:
        while True:
            line = process.stdout.readline()
            if line:
                pass
            else:
                time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping tunnel...")
        process.terminate()
else:
    print("Could not establish tunnel URL.")
    process.poll()
    process.terminate()
