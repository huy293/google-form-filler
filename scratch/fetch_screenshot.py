import requests
import base64
import os

url = "https://google-form-filler-lydg.onrender.com/test-form"
try:
    res = requests.get(url, timeout=25)
    data = res.json()
    if data.get("success"):
        img_b64 = data.get("screenshot", "").replace("data:image/png;base64,", "")
        if img_b64:
            img_data = base64.b64decode(img_b64)
            dest_path = r"C:\Users\luuhu\.gemini\antigravity\brain\9a082b5b-7b07-44e0-92e0-6d0e85421650\live_form_view.png"
            with open(dest_path, "wb") as f:
                f.write(img_data)
            print("Successfully saved screenshot to:", dest_path)
    else:
        print("Failed on server:", data.get("error"))
except Exception as e:
    print("Failed to query test-form:", e)
