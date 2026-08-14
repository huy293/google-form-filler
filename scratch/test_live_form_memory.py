import time
import requests
import base64
import os

print("Waiting for deployment to complete...")
time.sleep(30)  # Wait for build to progress

# Wait up to 5 minutes for status code 200 on health
url_health = "https://google-form-filler-lydg.onrender.com/health"
health_ok = False

for i in range(20):
    try:
        print(f"[{i * 15}s] Querying health...")
        response = requests.get(url_health, timeout=5)
        if response.status_code == 200:
            print("Server is Live!")
            health_ok = True
            break
    except Exception as e:
        print(f"[{i * 15}s] Server not ready: {e}")
    time.sleep(15)

if health_ok:
    # Query test-form
    url_form = "https://google-form-filler-lydg.onrender.com/test-form"
    print("\nQuerying test-form on live server...")
    try:
        response = requests.get(url_form, timeout=30)
        print("Status Code:", response.status_code)
        data = response.json()
        print("Success:", data.get("success"))
        if data.get("success"):
            print("Title:", data.get("title"))
            print("Elapsed seconds:", data.get("elapsed_seconds"))
            
            # Save screenshot
            img_b64 = data.get("screenshot", "").replace("data:image/png;base64,", "")
            if img_b64:
                img_data = base64.b64decode(img_b64)
                dest_path = r"C:\Users\luuhu\.gemini\antigravity\brain\9a082b5b-7b07-44e0-92e0-6d0e85421650\live_form_view.png"
                with open(dest_path, "wb") as f:
                    f.write(img_data)
                print(f"Saved screenshot to: {dest_path}")
        else:
            print("Error details:", data.get("error"))
    except Exception as e:
        print("Request failed:", e)
else:
    print("Could not complete health check.")
