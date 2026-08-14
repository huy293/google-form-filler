import sys
import asyncio
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8')

async def inspect():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("Navigating to form...")
        await page.goto("https://docs.google.com/forms/d/e/1FAIpQLSeXLQCQG6siLjJZZ4ZTxVcNpOYymwh5-Yw34HeK45HAp3ohog/viewform", wait_until="load")
        
        # 1. Date container input type
        date_container = page.locator('div[data-params*="1707290555"]')
        inputs = await date_container.locator('input').all()
        for idx, inp in enumerate(inputs):
            print(f"Date Input #{idx}: type='{await inp.get_attribute('type')}', label='{await inp.get_attribute('aria-label')}', class='{await inp.get_attribute('class')}'")
            
        # 2. Time container input type
        time_container = page.locator('div[data-params*="1773051864"]')
        time_inputs = await time_container.locator('input').all()
        for idx, inp in enumerate(time_inputs):
            print(f"Time Input #{idx}: type='{await inp.get_attribute('type')}', label='{await inp.get_attribute('aria-label')}', class='{await inp.get_attribute('class')}'")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect())
