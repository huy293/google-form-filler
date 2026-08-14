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
        
        # Get date container 1707290555 (Ngày đến)
        container = page.locator('div[data-params*="1707290555"]')
        html = await container.inner_html()
        print("Date Container HTML:")
        print(html[:2000]) # print first 2000 chars of HTML
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect())
