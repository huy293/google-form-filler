import requests

import json
url = "https://google-form-filler-lydg.onrender.com/status"
try:
    res = requests.get(url, timeout=10)
    print("Status Code:", res.status_code)
    print("Response JSON:", json.dumps(res.json(), ensure_ascii=True))
except Exception as e:
    print("Error querying status:", e)
