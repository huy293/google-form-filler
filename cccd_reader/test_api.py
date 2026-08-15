import requests, json, base64, cv2, numpy as np
from pathlib import Path

test_img = Path(r'C:\Users\luuhu\.gemini\antigravity\scratch\google-form-filler\cccd_reader\new_cc_clean.png')

with open(test_img, 'rb') as f:
    r = requests.post('http://localhost:5000/api/extract',
                      files={'image': ('test.jpg', f, 'image/jpeg')},
                      timeout=30)

data = r.json()
print(f'Status: {r.status_code}')
print(f'Layout: {data.get("layout")}')
print(f'Fields detected:')
for k, v in data.get('fields', {}).items():
    print(f'  {k}: {repr(v[:40]) if v else "(empty)"}')

crops = data.get('crops', {})
print(f'\nCrops: {len(crops)} fields')

# Save crops to disk to verify
out = Path('crops_api_test')
out.mkdir(exist_ok=True)
for k, b64 in crops.items():
    img_bytes = base64.b64decode(b64)
    arr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    cv2.imwrite(str(out / f'{k}.jpg'), img)
    print(f'  Saved: {k}.jpg  ({img.shape[1]}x{img.shape[0]})')

print(f'\nAPI working! Open browser: http://localhost:5000')
