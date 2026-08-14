import time
import requests
import base64
import os

print("Waiting for deployment to complete...")
time.sleep(30)  # Wait for build to start/progress

# Wait up to 5 minutes for status code 200
url = "https://google-form-filler-lydg.onrender.com/test-form"
success = False

for i in range(20):
    try:
        print(f"[{i * 15}s] Querying test-form...")
        response = requests.get(url, timeout=25)
        print(f"Status Code: {response.status_code}")
        data = response.json()
        if data.get("success"):
            print("Success!")
            print("Title:", data.get("title"))
            print("Elapsed seconds:", data.get("elapsed_seconds"))
            
            # Save screenshot
            img_b64 = data.get("screenshot", "").replace("data:image/png;base64,", "")
            if img_b64:
                img_data = base64.b64decode(img_b64)
                # Save to artifacts directory for visualization
                artifact_dir = r"C:\Users\luuhu\.gemini\antigravity\brain\9a082b5b-7b07-44e0-92e0-6d0e85421650"
                os.makedirs(artifact_dir, exist_ok=True)
                dest_path = os.path.join(artifact_dir, "live_form_view.png")
                with open(dest_path, "wb") as f:
                    f.write(img_data)
                print(f"Saved screenshot to: {dest_path}")
            success = True
            break
        else:
            print("Error from server:", data.get("error"))
    except Exception as e:
        print(f"Failed to connect: {e}")
    time.sleep(15)

if not success:
    print("Could not complete test-form query.")
