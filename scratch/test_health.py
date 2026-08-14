import requests

try:
    response = requests.get("https://google-form-filler-lydg.onrender.com/", timeout=10)
    print("Status Code:", response.status_code)
    print("Response Length:", len(response.text))
except Exception as e:
    print("Error querying root endpoint:", e)
