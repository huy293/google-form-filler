"""
Download passport images from Wikimedia Commons (public domain)
These are official passport specimen images from government sources
"""
import requests, re, os
from pathlib import Path
from urllib.parse import quote

OUT = Path('passport_web')
OUT.mkdir(exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; ResearchBot/1.0)'
}

# Wikimedia Commons API - tim anh passport mau
COMMONS_API = 'https://commons.wikimedia.org/w/api.php'

def search_commons(query, limit=50):
    """Tim anh tren Wikimedia Commons"""
    params = {
        'action': 'query',
        'list': 'search',
        'srsearch': query,
        'srnamespace': 6,  # File namespace
        'srlimit': limit,
        'format': 'json'
    }
    r = requests.get(COMMONS_API, params=params, headers=HEADERS, timeout=15)
    if r.status_code != 200:
        return []
    data = r.json()
    return data.get('query', {}).get('search', [])

def get_image_url(filename):
    """Lay URL anh goc tu Commons"""
    params = {
        'action': 'query',
        'titles': filename,
        'prop': 'imageinfo',
        'iiprop': 'url|size|mediatype',
        'format': 'json'
    }
    r = requests.get(COMMONS_API, params=params, headers=HEADERS, timeout=15)
    if r.status_code != 200:
        return None
    data = r.json()
    pages = data.get('query', {}).get('pages', {})
    for page in pages.values():
        ii = page.get('imageinfo', [])
        if ii:
            info = ii[0]
            # Chi lay anh JPG/PNG khong qua nho
            if info.get('size', 0) > 50000:  # >50KB
                return info.get('url')
    return None

def download(url, path):
    if path.exists():
        return True
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.ok and len(r.content) > 10000:
            path.write_bytes(r.content)
            return True
    except Exception as e:
        print(f'  ERR: {e}')
    return False

# Queries de tim anh passport mau
QUERIES = [
    'passport biographical data page specimen',
    'passport identity page sample official',
    'Vietnamese passport specimen',
    'British passport biographical page',
    'German passport data page',
    'French passport specimen page',
    'Australian passport biographical',
    'Japanese passport sample page',
    'Korean passport specimen',
    'passport MRZ machine readable zone',
    'passport photo page official',
    'biometric passport data page',
]

total = 0
all_files = set()

for query in QUERIES:
    print(f'\nSearching: {query}')
    results = search_commons(query, limit=30)
    print(f'  Found {len(results)} results')
    
    for item in results:
        title = item['title']
        if title in all_files:
            continue
        all_files.add(title)
        
        # Chi lay file anh
        ext = title.lower().split('.')[-1]
        if ext not in ('jpg', 'jpeg', 'png'):
            continue
        
        img_url = get_image_url(title)
        if not img_url:
            continue
        
        # Dat ten file
        safe_name = re.sub(r'[^\w.-]', '_', title.replace('File:', ''))[:80]
        ext_final = 'jpg' if 'jpg' in ext or 'jpeg' in ext else 'png'
        save_path = OUT / f'{safe_name}.{ext_final}'
        
        ok = download(img_url, save_path)
        if ok:
            total += 1
            size_kb = save_path.stat().st_size // 1024
            print(f'  [+] {safe_name[:50]} ({size_kb}KB) total={total}')
        
        import time
        time.sleep(0.3)

print(f'\n=== DONE: {total} images -> {OUT}/ ===')
