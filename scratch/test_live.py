import requests
import json

url = "https://google-form-filler-lydg.onrender.com/api/submit"
data = {
    "unitCode": "A19.999",
    "guestId": "TEST123456",
    "gender": "male"
}

print("Sending registration request to live server...")
try:
    response = requests.post(url, json=data, timeout=35)
    print("Status Code:", response.status_code)
    res_data = response.json()
    if "success" in res_data:
        print("Success:", res_data["success"])
        if res_data["success"]:
            print("Guest Name:", res_data["guestName"])
            print("Filled image length:", len(res_data.get("screenshot_filled", "")))
            print("Submitted image length:", len(res_data.get("screenshot_submitted", "")))
        else:
            print("Error details:", res_data.get("error"))
    else:
        print("Unexpected Response:", res_data)
except Exception as e:
    print("Error connecting to live server:", e)
