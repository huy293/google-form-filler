import time
import requests

print("Monitoring health endpoint for up to 6 minutes...")
start_time = time.time()

while time.time() - start_time < 360:
    elapsed = int(time.time() - start_time)
    try:
        response = requests.get("https://google-form-filler-lydg.onrender.com/health", timeout=5)
        print(f"[{elapsed}s] Response status code:", response.status_code)
        print(f"[{elapsed}s] Response content:", response.json())
        if response.status_code == 200:
            print("Successfully connected to the updated server!")
            
            # Now test the browser
            print("Testing browser automation...")
            try:
                tb_response = requests.get("https://google-form-filler-lydg.onrender.com/test-browser", timeout=20)
                print("Test-Browser status:", tb_response.status_code)
                print("Test-Browser JSON:", tb_response.json())
            except Exception as e:
                print("Test-Browser request failed:", e)
            break
    except Exception as e:
        print(f"[{elapsed}s] Server not ready yet or returned error: {e}")
    time.sleep(15)

print("Monitoring finished.")
