"""
PRADO scraper dung undetected-chromedriver (UC) - vuot bot detection manh hon
"""
import undetected_chromedriver as uc
import re, time, random, requests
from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE = 'https://www.consilium.europa.eu/prado'
OUT  = Path('prado_passports')
OUT.mkdir(exist_ok=True)

COUNTRIES = [
    'VNM','GBR','FRA','DEU','AUS','JPN','KOR',
    'IND','ITA','ESP','NLD','CHE','SWE','NOR',
    'THA','SGP','MYS','IDN','PHL',
]

def wait_cf(driver, url, timeout=30):
    """Load URL, wait for CF challenge"""
    driver.get(url)
    start = time.time()
    while time.time() - start < timeout:
        title = driver.title
        if 'browser check' not in title.lower() and 'just a moment' not in title.lower():
            break
        print(f'  [CF] {title}...')
        time.sleep(3)
    print(f'  Title: {driver.title}')
    return driver.page_source

def get_cookies_dict(driver):
    return {c['name']: c['value'] for c in driver.get_cookies()}

def run():
    print('Starting undetected Chrome...')
    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1366,768')
    options.add_argument('--lang=en-US')
    
    driver = uc.Chrome(options=options, headless=True, version_main=151)
    session = requests.Session()
    
    try:
        # B1: Load trang chinh de lay cookie
        print('\n=== Loading PRADO ===')
        html = wait_cf(driver, f'{BASE}/en/search-by-document-country.html')
        print(f'HTML length: {len(html)}')
        
        # Lay cookie tu browser -> requests
        cookies = get_cookies_dict(driver)
        session.cookies.update(cookies)
        session.headers.update({
            'User-Agent': driver.execute_script('return navigator.userAgent'),
            'Referer': f'{BASE}/en/search-by-document-country.html',
        })
        
        # Tim quoc gia
        countries = list(dict.fromkeys(re.findall(r'prado-documents/([A-Z]{3})/', html)))
        print(f'Countries: {len(countries)}: {countries[:10]}')
        if not countries:
            countries = COUNTRIES
        
        total = 0
        
        for country in countries:
            print(f'\n=== {country} ===')
            c_html = wait_cf(driver, f'{BASE}/en/prado-documents/{country}/')
            
            all_docs = list(dict.fromkeys(
                re.findall(rf'prado-documents/{country}/([A-Z0-9-]+)/', c_html)
            ))
            passport_docs = [d for d in all_docs if d.startswith('RP-')]
            print(f'  Passport docs: {passport_docs}')
            
            for doc in passport_docs:
                d_dir = OUT / country / doc
                d_dir.mkdir(parents=True, exist_ok=True)
                
                d_html = wait_cf(driver, f'{BASE}/en/prado-documents/{country}/{doc}/index.html')
                
                imgs = re.findall(r'src="(/prado/images/[^"]+\.jpg)"', d_html)
                full_imgs = [f'https://www.consilium.europa.eu{u}'
                            for u in set(imgs) if '_thumb' not in u]
                print(f'  {doc}: {len(full_imgs)} images')
                
                # Lay cookie moi nhat
                cookies = get_cookies_dict(driver)
                session.cookies.update(cookies)
                
                for i, img_url in enumerate(full_imgs):
                    fname = d_dir / f'{country}_{doc}_{i+1:03d}.jpg'
                    if fname.exists(): continue
                    try:
                        r = session.get(img_url, timeout=20)
                        if r.ok and len(r.content) > 5000:
                            fname.write_bytes(r.content)
                            total += 1
                            print(f'    [+] {fname.name} ({len(r.content)//1024}KB) total={total}')
                        else:
                            print(f'    [-] {r.status_code} {img_url}')
                    except Exception as e:
                        print(f'    [!] {e}')
                    time.sleep(random.uniform(0.5, 1.0))
            
            time.sleep(random.uniform(1, 2))
        
        print(f'\n=== DONE: {total} images -> {OUT} ===')
    
    finally:
        driver.quit()

run()
