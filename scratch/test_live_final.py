import time
import requests

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
    data = {
        "unitCode": "A19.999",
        "guestId": "TEST123456",
        "gender": "male"
    }
    print("\nSending registration request to live server...")
    try:
        response = requests.post(url_submit, json=data, timeout=35)
        print("Status Code:", response.status_code)
        res_data = response.json()
        print("Success:", res_data.get("success"))
        if res_data.get("success"):
            print("Guest Name:", res_data.get("guestName"))
            print("Filled image length:", len(res_data.get("screenshot_filled", "")))
            print("Submitted image length:", len(res_data.get("screenshot_submitted", "")))
        else:
            print("Error details:", res_data.get("error"))
    except Exception as e:
        print("Request failed:", e)
else:
    print("Could not complete health check.")
