"""
PRADO Scraper v4 - stealth qua apply_stealth_async, doi Cloudflare
"""
import asyncio, re, random
from pathlib import Path
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

BASE = 'https://www.consilium.europa.eu/prado'
OUT  = Path('prado_passports')
OUT.mkdir(exist_ok=True)

COUNTRIES = [
    'VNM','GBR','FRA','DEU','AUS','JPN','KOR','IND',
    'ITA','ESP','NLD','CHE','SWE','NOR','POL','TUR',
    'THA','SGP','MYS','IDN','PHL','BRA','MEX','ZAF',
]

STEALTH = Stealth(
    navigator_webdriver=True,
    navigator_user_agent=True,
    navigator_vendor=True,
    chrome_runtime=True,
)

async def wait_cf(page, url, max_wait=40):
    """Load URL, wait for Cloudflare to pass"""
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=35000)
    except Exception as e:
        print(f'  nav err: {e}')
    
    for i in range(max_wait // 3):
        title = await page.title()
        if 'moment' not in title.lower() and 'checking' not in title.lower():
            break
        print(f'  [CF {i*3}s] {title}')
        await asyncio.sleep(3)
    
    return await page.content()

async def scrape():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
            ]
        )
        ctx = await browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
            locale='en-US',
        )
        page = await ctx.new_page()
        
        # Apply stealth to page
        await STEALTH.apply_stealth_async(page)
        
        # Extra anti-detection
        await page.add_init_script("""
            delete Object.getPrototypeOf(navigator).webdriver;
            Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });
            window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
        """)

        # B1: Load trang chinh
        print('=== PRADO stealth ===')
        html = await wait_cf(page, f'{BASE}/en/search-by-document-country.html')
        title = await page.title()
        print(f'Title: "{title}" | HTML: {len(html)}')
        
        # Save debug
        Path('prado_debug.html').write_text(html[:4000], encoding='utf-8', errors='ignore')
        
        # Tim cac nuoc
        countries_found = list(dict.fromkeys(re.findall(r'prado-documents/([A-Z]{3})/', html)))
        print(f'Countries found: {len(countries_found)}: {countries_found[:15]}')
        countries = countries_found if len(countries_found) > 5 else COUNTRIES
        
        total = 0
        
        for country in countries:
            print(f'\n=== {country} ===')
            c_html = await wait_cf(page, f'{BASE}/en/prado-documents/{country}/')
            
            all_docs = list(dict.fromkeys(
                re.findall(rf'prado-documents/{country}/([A-Z0-9-]+)/', c_html)
            ))
            passport_docs = [d for d in all_docs if d.startswith('RP-')]
            print(f'  Passport: {passport_docs}')
            
            for doc in passport_docs:
                d_dir = OUT / country / doc
                d_dir.mkdir(parents=True, exist_ok=True)
                
                d_html = await wait_cf(page, f'{BASE}/en/prado-documents/{country}/{doc}/index.html')
                
                imgs = re.findall(r'src="(/prado/images/[^"]+\.jpg)"', d_html)
                full_imgs = [f'https://www.consilium.europa.eu{u}'
                            for u in set(imgs) if '_thumb' not in u]
                print(f'  {doc}: {len(full_imgs)} images')
                
                for i, url in enumerate(full_imgs):
                    fname = d_dir / f'{country}_{doc}_{i+1:03d}.jpg'
                    if fname.exists(): continue
                    try:
                        r = await ctx.request.get(url)
                        if r.ok:
                            fname.write_bytes(await r.body())
                            total += 1
                            print(f'    [+] {fname.name} total={total}')
                        else:
                            print(f'    [-] {r.status}')
                    except Exception as e:
                        print(f'    [!] {e}')
                    await asyncio.sleep(random.uniform(0.5, 1.0))
            
            await asyncio.sleep(random.uniform(1, 2.5))
        
        await browser.close()
        print(f'\n=== DONE: {total} images -> {OUT} ===')

asyncio.run(scrape())
