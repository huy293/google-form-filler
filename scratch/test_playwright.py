import asyncio
import main
from playwright.async_api import async_playwright
from main import fill_form_playwright, SubmitRequest

async def test():
    req = SubmitRequest(
        unitCode="A8.10",
        guestId="PL4186782",
        gender="female"
    )
    print("Testing Playwright form filler locally...")
    
    # Initialize global browser for local test
    main.GLOBAL_PLAYWRIGHT = await async_playwright().start()
    main.GLOBAL_BROWSER = await main.GLOBAL_PLAYWRIGHT.chromium.launch(
        headless=True  # Force headless in agent environment
    )
    
    try:
        res = await fill_form_playwright(req)
        print("Result:", res.get("success"), res.get("error", "No error"))
        if res.get("success"):
            print("Success! Got screenshots.")
            print("Filled screenshot prefix:", res["screenshot_filled"][:50])
            print("Submitted screenshot prefix:", res["screenshot_submitted"][:50])
        else:
            print("Failed!")
    finally:
        await main.GLOBAL_BROWSER.close()
        await main.GLOBAL_PLAYWRIGHT.stop()

if __name__ == "__main__":
    asyncio.run(test())
