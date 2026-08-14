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
        
        # Find all divs with role="button"
        buttons = await page.locator('div[role="button"]').all()
        print(f"Found {len(buttons)} buttons with role='button':")
        for idx, btn in enumerate(buttons):
            text = await btn.inner_text()
            html = await btn.evaluate("el => el.outerHTML")
            print(f"Button #{idx}: text='{text}', html='{html[:150]}...'")
            
        # Find all spans containing "Gửi" or "Submit"
        spans = await page.locator('span').all()
        for span in spans:
            text = await span.inner_text()
            if text in ["Gửi", "Submit"]:
                html = await span.evaluate("el => el.outerHTML")
                print(f"Found matching span: text='{text}', html='{html}'")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect())
