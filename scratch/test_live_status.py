import time
import requests
import threading

print("Waiting for deployment to complete...")
time.sleep(30)  # Wait for build to progress

# Wait up to 5 minutes for status code 200 on health
url_health = "https://google-form-filler-lydg.onrender.com/health"
health_ok = False

for i in range(20):
    try:
        response = requests.get(url_health, timeout=5)
        if response.status_code == 200:
            print("Server is Live!")
            health_ok = True
            break
    except Exception as e:
        print(f"[{i * 15}s] Server not ready: {e}")
    time.sleep(15)

if health_ok:
    url_submit = "https://google-form-filler-lydg.onrender.com/api/submit"
    url_status = "https://google-form-filler-lydg.onrender.com/status"
    
    data = {
        "unitCode": "A19.999",
        "guestId": "TEST123456",
        "gender": "male"
    }
    
    def trigger_submit():
        print("[Submit Thread] Sending submit request...")
        try:
            res = requests.post(url_submit, json=data, timeout=35)
            print("[Submit Thread] Status:", res.status_code)
            print("[Submit Thread] JSON:", res.json())
        except Exception as e:
            print("[Submit Thread] Request finished or failed:", e)
            
    # Trigger submit in a background thread
    t = threading.Thread(target=trigger_submit)
    t.start()
    
    # Query status every 2 seconds for 30 seconds
    for step in range(16):
        time.sleep(2)
        try:
            status_res = requests.get(url_status, timeout=5)
            print(f"[Status Check {step}] Logs:", status_res.json().get("logs"))
        except Exception as e:
            print(f"[Status Check {step}] Failed to query status:", e)
            
    t.join()
else:
    print("Could not complete health check.")
