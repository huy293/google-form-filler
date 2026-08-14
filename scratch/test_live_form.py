import requests
import base64
import os

url = "https://google-form-filler-lydg.onrender.com/test-form"
print("Querying test-form endpoint on live server...")
try:
    response = requests.get(url, timeout=30)
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
