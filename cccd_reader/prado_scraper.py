"""
PRADO Passport Image Scraper
Lay anh ho chieu tu: https://www.consilium.europa.eu/prado
"""
import requests, re, os, time, random
from pathlib import Path

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
    'Referer': 'https://www.consilium.europa.eu/prado/en/search-by-document-country.html',
}
BASE = 'https://www.consilium.europa.eu/prado'
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

def get(url, **kw):
    try:
        r = SESSION.get(url, timeout=20, **kw)
        print(f'  GET {url[:80]} -> {r.status_code}')
        return r
    except Exception as e:
        print(f'  ERROR {url}: {e}')
        return None

def fetch_country_list():
    """Lay danh sach quoc gia co ho chieu tren PRADO"""
    r = get(f'{BASE}/en/search-by-document-country.html')
    if not r or r.status_code != 200:
        print(f'Cannot fetch country list: {r.status_code if r else "no response"}')
        return []
    
    # Tim cac link quoc gia
    # Pattern: /prado/en/prado-documents/VNM/ hoac tuong tu
    countries = re.findall(r'/prado/en/prado-documents/([A-Z]{3})/', r.text)
    countries = list(dict.fromkeys(countries))  # unique, preserve order
    print(f'Found {len(countries)} countries: {countries[:10]}...')
    return countries

def fetch_passport_docs(country_code):
    """Lay danh sach ho chieu (RP = Regular Passport) cua 1 quoc gia"""
    url = f'{BASE}/en/prado-documents/{country_code}/'
    r = get(url)
    if not r or r.status_code != 200:
        return []
    
    # Tim doc codes, passport thường có 'RP' trong code
    docs = re.findall(r'/prado/en/prado-documents/' + country_code + r'/([A-Z0-9-]+)/', r.text)
    docs = list(dict.fromkeys(docs))
    passports = [d for d in docs if 'RP' in d or 'PA' in d or 'PP' in d]
    print(f'  {country_code}: {len(passports)} passport docs: {passports}')
    return passports

def fetch_doc_images(country_code, doc_code):
    """Lay tat ca anh cua 1 loai ho chieu"""
    url = f'{BASE}/en/prado-documents/{country_code}/{doc_code}/index.html'
    r = get(url)
    if not r or r.status_code != 200:
        return []
    
    # Tim image URLs
    imgs = re.findall(r'src="([^"]*image[^"]*\.jpg)"', r.text)
    imgs += re.findall(r"src='([^']*image[^']*\.jpg)'", r.text)
    imgs = list(dict.fromkeys(imgs))
    
    # Normalize URLs
    full_urls = []
    for img in imgs:
        if img.startswith('http'):
            full_urls.append(img)
        elif img.startswith('/'):
            full_urls.append(f'https://www.consilium.europa.eu{img}')
        else:
            full_urls.append(f'{BASE}/{img}')
    
    # Chi lay anh trang bao-data (bo qua thumb, UV, IR...)
    # Lọc: lay anh full size (khong co _thumb)
    full_imgs = [u for u in full_urls if '_thumb' not in u]
    print(f'    {doc_code}: {len(full_imgs)} full images')
    return full_imgs

def download_image(url, save_path):
    """Download 1 anh"""
    if save_path.exists():
        return True
    r = get(url)
    if not r or r.status_code != 200:
        return False
    save_path.write_bytes(r.content)
    return True


if __name__ == '__main__':
    import sys
    
    out_dir = Path('prado_passports')
    out_dir.mkdir(exist_ok=True)
    
    # --- B1: Lay danh sach quoc gia ---
    print('=== Fetching country list ===')
    countries = fetch_country_list()
    
    if not countries:
        # Fallback: thu voi mot so nuoc lon
        countries = ['VNM','GBR','FRA','DEU','USA','AUS','JPN','KOR','CHN','IND',
                     'ITA','ESP','PRT','NLD','BEL','CHE','AUT','POL','CZE','HUN']
        print(f'Using fallback list: {countries}')
    
    total = 0
    for country in countries:
        print(f'\n=== {country} ===')
        passport_docs = fetch_passport_docs(country)
        
        for doc in passport_docs:
            img_dir = out_dir / country / doc
            img_dir.mkdir(parents=True, exist_ok=True)
            
            imgs = fetch_doc_images(country, doc)
            for i, img_url in enumerate(imgs):
                fname = f'{country}_{doc}_img{i+1:03d}.jpg'
                save_path = img_dir / fname
                ok = download_image(img_url, save_path)
                if ok:
                    total += 1
                    print(f'    [OK] {fname} (total={total})')
                time.sleep(random.uniform(0.5, 1.5))  # Polite delay
        
        time.sleep(random.uniform(1, 2))
    
    print(f'\n=== DONE: {total} images saved to {out_dir}/ ===')
