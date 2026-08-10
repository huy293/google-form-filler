import os
import io
import sys
import base64
import random
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from playwright.async_api import async_playwright
from contextlib import asynccontextmanager

# Configure console to support Vietnamese output
sys.stdout.reconfigure(encoding='utf-8')

# Lists of names and addresses for realistic randomization
REP_MALE_NAMES = ["Nguyễn Văn Hùng", "Trần Minh Tuấn", "Lê Hoàng Nam", "Phạm Quốc Bảo", "Nguyễn Hải Dương", "Trần Việt Anh", "Đỗ Minh Đức", "Vũ Huy Hoàng", "Nguyễn Hữu Đạt", "Lê Gia Bách"]
REP_FEMALE_NAMES = ["Nguyễn Thị Mai", "Trần Thu Trang", "Lê Linh Chi", "Phạm Hải Yến", "Nguyễn Khánh An", "Trần Mỹ Linh", "Đỗ Vân Anh", "Vũ Phương Thảo", "Lê Mai Hương", "Phạm Quỳnh Chi"]

GUEST_MALE_NAMES = ["Bennan", "John", "David", "Alex", "Michael", "James", "Robert", "William", "Peter", "Thomas", "Paul", "Daniel", "Chris", "Nguyễn Văn Nam", "Trần Hoàng Bách", "Lê Tuấn Kiệt"]
GUEST_FEMALE_NAMES = ["Agne", "Amada", "Mary", "Anna", "Linda", "Elizabeth", "Sarah", "Jessica", "Karen", "Lisa", "Helen", "Sandra", "Emily", "Trần Thu Thảo", "Nguyễn Mai Anh", "Lê Vy"]

ADDRESSES = [
    "123 Nguyễn Trãi, Quận 5, TP.HCM",
    "456 Lê Lợi, Quận 1, TP.HCM",
    "789 Cách Mạng Tháng 8, Quận 3, TP.HCM",
    "101 Trần Hưng Đạo, Quận 1, TP.HCM",
    "Rivergate Residence, Quận 4, TP.HCM",
    "202 Bến Vân Đồn, Quận 4, TP.HCM",
    "15 Hoàng Diệu, Quận 4, TP.HCM",
    "368 Nguyễn Thị Minh Khai, Quận 3, TP.HCM"
]

NATIONALITIES = ["Lithuania", "USA", "Hàn Quốc", "Việt Nam", "Đức", "Anh", "Nhật Bản", "Đài Loan", "Trung Quốc"]

submit_lock = asyncio.Lock()

# Global browser singleton for speed and low RAM usage on Render
GLOBAL_PLAYWRIGHT = None
GLOBAL_BROWSER = None

async def get_browser():
    global GLOBAL_PLAYWRIGHT, GLOBAL_BROWSER
    if GLOBAL_PLAYWRIGHT is None:
        print("Starting global Playwright...")
        GLOBAL_PLAYWRIGHT = await async_playwright().start()
        
    is_broken = False
    if GLOBAL_BROWSER is not None:
        try:
            # Test if browser is responsive by trying to open/close context
            ctx = await GLOBAL_BROWSER.new_context()
            await ctx.close()
        except Exception:
            print("Detected crashed or dead Chromium process. Re-launching...")
            is_broken = True
            
    if GLOBAL_BROWSER is None or is_broken or not GLOBAL_BROWSER.is_connected():
        print("Browser is disconnected or broken. Starting new Chromium instance...")
        if GLOBAL_BROWSER:
            try:
                await GLOBAL_BROWSER.close()
            except Exception:
                pass
            GLOBAL_BROWSER = None
            
        launch_args = []
        if os.name != 'nt':  # Linux/Docker
            launch_args = [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--single-process",
                "--js-flags=--max-old-space-size=128",
                "--disable-extensions",
                "--disable-default-apps"
            ]
        is_headless = os.name != 'nt'
        GLOBAL_BROWSER = await GLOBAL_PLAYWRIGHT.chromium.launch(
            headless=is_headless,
            args=launch_args
        )
        print("New Chromium instance started successfully!")
        
    return GLOBAL_BROWSER

async def force_relaunch_browser():
    global GLOBAL_PLAYWRIGHT, GLOBAL_BROWSER
    print("Force relaunching browser singleton...")
    if GLOBAL_BROWSER:
        try:
            await GLOBAL_BROWSER.close()
        except Exception:
            pass
        GLOBAL_BROWSER = None
    if GLOBAL_PLAYWRIGHT:
        try:
            await GLOBAL_PLAYWRIGHT.stop()
        except Exception:
            pass
        GLOBAL_PLAYWRIGHT = None
    await get_browser()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm browser on startup
    try:
        await get_browser()
    except Exception as e:
        print(f"Error pre-warming browser: {e}")
        
    yield
    
    # Shutdown logic
    global GLOBAL_PLAYWRIGHT, GLOBAL_BROWSER
    if GLOBAL_BROWSER:
        print("Closing global Chromium browser...")
        try:
            await GLOBAL_BROWSER.close()
        except Exception:
            pass
    if GLOBAL_PLAYWRIGHT:
        print("Stopping global Playwright...")
        try:
            await GLOBAL_PLAYWRIGHT.stop()
        except Exception:
            pass

app = FastAPI(title="Google Form Auto-Filler Web API", lifespan=lifespan)

@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h3>Error: static/index.html not found!</h3>"

@app.get("/health")
async def health_check():
    global GLOBAL_BROWSER
    is_ok = GLOBAL_BROWSER is not None and GLOBAL_BROWSER.is_connected()
    return {
        "status": "healthy",
        "browser_initialized": is_ok
    }

@app.get("/test-browser")
async def test_browser():
    try:
        browser = await get_browser()
        context = await browser.new_context()
        page = await context.new_page()
        print("Test browser: navigating to example.com...")
        await page.goto("https://example.com", wait_until="load", timeout=10000)
        title = await page.title()
        await context.close()
        return {"success": True, "title": title}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/test-form")
async def test_form():
    try:
        # Emulate phone layout using custom lightweight viewport
        context = await browser.new_context(
            viewport={"width": 393, "height": 851},
            is_mobile=True,
            has_touch=True
        )
        page = await context.new_page()
        print("Test form: navigating to Google Form...")
        start_time = datetime.now()
        await page.goto("https://docs.google.com/forms/d/e/1FAIpQLSeXLQCQG6siLjJZZ4ZTxVcNpOYymwh5-Yw34HeK45HAp3ohog/viewform", wait_until="load", timeout=20000)
        elapsed = (datetime.now() - start_time).total_seconds()
        title = await page.title()
        
        # Take a screenshot to see what it actually displays
        screenshot_bytes = await page.screenshot(type="png", full_page=False)
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
        
        await context.close()
        return {
            "success": True,
            "title": title,
            "elapsed_seconds": elapsed,
            "screenshot": f"data:image/png;base64,{screenshot_b64}"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

RUNNING_LOGS = []

def log_step(step_name):
    global RUNNING_LOGS
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    msg = f"[{timestamp}] {step_name}"
    RUNNING_LOGS.append(msg)
    print(msg)

@app.get("/status")
async def get_status():
    global RUNNING_LOGS
    return {"logs": RUNNING_LOGS}

class SubmitRequest(BaseModel):
    unitCode: str
    guestId: str
    gender: str

async def fill_form_playwright(data: SubmitRequest):
    # 1. Generate random values
    rep_gender = random.choice(["male", "female"])
    rep_name = random.choice(REP_MALE_NAMES) if rep_gender == "male" else random.choice(REP_FEMALE_NAMES)
    
    phone_prefix = random.choice(["09", "03", "07", "08", "05"])
    phone_suffix = "".join(random.choice("0123456789") for _ in range(8))
    rep_phone = phone_prefix + phone_suffix
    
    gender = data.gender.lower()
    guest_name = random.choice(GUEST_MALE_NAMES) if gender == "male" else random.choice(GUEST_FEMALE_NAMES)
    
    birth_year = random.randint(1960, 2010)
    
    # Check if guest name is foreign
    is_foreign = guest_name in GUEST_MALE_NAMES[:13] or guest_name in GUEST_FEMALE_NAMES[:13]
    if is_foreign:
        nation = random.choice(["Lithuania", "USA", "Đức", "Anh", "Hàn Quốc"])
    else:
        nation = "Việt Nam"
        
    visa_letter = random.choice(["V", "DL", "EV"])
    visa_number = "".join(random.choice("0123456789") for _ in range(7))
    visa = visa_letter + visa_number
    
    # Dates
    today = datetime.now()
    check_in_date = today.strftime("%Y-%m-%d")
    
    # Check-in time + 30 mins
    time_in = today + timedelta(minutes=30)
    check_in_time = time_in.strftime("%H:%M")
    
    # Check-out date + 1 to 3 days
    checkout_days = random.randint(1, 3)
    check_out_date = (today + timedelta(days=checkout_days)).strftime("%Y-%m-%d")
    
    # Visa Expiry
    visa_exp_date = (today + timedelta(days=random.randint(30, 90))).strftime("%Y-%m-%d")
    
    address = random.choice(ADDRESSES)
    
    # Pack row data
    row_data = {
        "Họ và tên người đăng ký": rep_name,
        "Số điện thoại người đăng ký": rep_phone,
        "Họ và tên khách": guest_name,
        "Năm sinh": str(birth_year),
        "Mã Căn Hộ": data.unitCode,
        "Hộ Chiếu_CCCD": data.guestId,
        "VISA": visa,
        "Hạn VISA": visa_exp_date,
        "Quốc tịch": nation,
        "Thông tin hộ khẩu": address,
        "Chủ thể": "Khách đến thăm/ Visitors",
        "Ngày đến": check_in_date,
        "Thời gian vào": check_in_time,
        "Ngày ra": check_out_date,
        "Cam kết tuân thủ": "Tôi đã đọc và đồng ý"
    }
    
    browser = await get_browser()

    # Create a new isolated context for this request (with auto-healing fallback and custom mobile viewport)
    try:
        context = await browser.new_context(
            viewport={"width": 393, "height": 851},
            is_mobile=True,
            has_touch=True
        )
    except Exception as e:
        print(f"Failed to create context: {e}. Force relaunching browser singleton...")
        await force_relaunch_browser()
        browser = await get_browser()
        context = await browser.new_context(
            viewport={"width": 393, "height": 851},
            is_mobile=True,
            has_touch=True
        )
        
    page = await context.new_page()
    
    try:
        global RUNNING_LOGS
        RUNNING_LOGS = []
        
        # Block analytics and ads to speed up load time
        await page.route("**/*", lambda route: 
            route.abort() if any(domain in route.request.url for domain in [
                "google-analytics.com", "googletagmanager.com", "analytics", 
                "collect?", "doubleclick.net", "googleadservices.com"
            ]) else route.continue_()
        )

        # Go to form
        log_step("1. Navigating to Google Form...")
        print(f"Navigating to form for guest {guest_name} ({data.guestId})...")
        await page.goto("https://docs.google.com/forms/d/e/1FAIpQLSeXLQCQG6siLjJZZ4ZTxVcNpOYymwh5-Yw34HeK45HAp3ohog/viewform", wait_until="domcontentloaded", timeout=20000)
        
        # 1. Fill basic text fields (including text-based Visa Expiry)
        log_step("2. Filling basic text fields (Name, Passport, Visa, etc.)...")
        fields_to_fill = {
            "Họ và tên người đăng ký": "178418221",
            "Số điện thoại người đăng ký": "2093418625",
            "Họ và tên khách": "955098140",
            "Năm sinh": "870248713",
            "Mã Căn Hộ": "175253502",
            "Hộ Chiếu_CCCD": "1388064463",
            "VISA": "2009586042",
            "Hạn VISA": "1149566062",
            "Quốc tịch": "1515902134",
            "Thông tin hộ khẩu": "2023500619"
        }
        
        for label, entry_id in fields_to_fill.items():
            val = row_data[label]
            if not val:
                continue
            container = page.locator(f'div[data-params*="{entry_id}"]')
            if await container.count() > 0 and await container.first.is_visible():
                input_el = container.locator('input[type="text"], textarea')
                if await input_el.count() > 0 and await input_el.first.is_visible():
                    await input_el.first.fill(str(val))
            
        # Dropdown: Chủ thể - 117977297
        log_step("3. Clicking dropdown subject...")
        container = page.locator('div[data-params*="117977297"]')
        await container.locator('div[role="listbox"]').first.click(force=True)
        await asyncio.sleep(0.05)
        # Select the target option (wait for options to be visible first)
        options = page.locator('div[role="option"]')
        await options.first.wait_for(state="visible", timeout=5000)
        target_option = options.filter(has_text="Khách đến thăm")
        if await target_option.count() > 0:
            await target_option.first.click(force=True)
        else:
            # Fallback to second option (index 1) since index 0 is the "Choose/Chọn" placeholder
            await options.nth(1).click(force=True)
        await asyncio.sleep(0.05)
        
        # Dates: Ngày đến, Ngày ra (Native HTML5 inputs)
        log_step("4. Filling check-in/out dates...")
        date_fields = {
            "Ngày đến": "1707290555",
            "Ngày ra": "1028902383"
        }
        
        for label, entry_id in date_fields.items():
            val = row_data[label] # YYYY-MM-DD
            container = page.locator(f'div[data-params*="{entry_id}"]')
            await container.locator('input[type="date"]').fill(val)
                
        # Time: Thời gian vào - 1773051864 (HH:MM)
        log_step("5. Filling check-in time...")
        time_val = row_data["Thời gian vào"]
        container = page.locator('div[data-params*="1773051864"]')
        native_time = container.locator('input[type="time"]')
        if await native_time.count() > 0:
            await native_time.fill(time_val)
        else:
            time_parts = time_val.split(':')
            if len(time_parts) == 2:
                hour, minute = time_parts[0], time_parts[1]
                # Target inputs generally (type can be text, tel, or number on mobile layout)
                await container.locator('input').nth(0).fill(hour)
                await container.locator('input').nth(1).fill(minute)
            
        # Agreement checkbox: Cam kết tuân thủ - 1651751105 (first checkbox click with force=True)
        log_step("6. Checking compliance checkbox...")
        container = page.locator('div[data-params*="1651751105"]')
        await container.locator('div[role="checkbox"], div[role="radio"]').first.click(force=True)
        await asyncio.sleep(0.05)
        
        # Settle and take first screenshot (filled form as compressed JPEG)
        log_step("7. Capturing filled form screenshot...")
        await page.evaluate("window.scrollTo(0, 0);")
        await asyncio.sleep(0.1)
        filled_bytes = await page.screenshot(type="jpeg", quality=50)
        screenshot_filled_b64 = base64.b64encode(filled_bytes).decode('utf-8')
        
        # Click submit (Unicode-independent class selection)
        log_step("8. Clicking Submit button...")
        submit_btn = page.locator('div[role="button"].Y5sE8d').first
        await submit_btn.click()
        
        # Wait for confirmation message wrapper or "Submit another response" link
        log_step("9. Waiting for confirmation page element...")
        await page.locator('.vHW8K, a[href*="viewform"]').first.wait_for(state="visible", timeout=10000)
        await asyncio.sleep(0.1)
        
        # Take submitted screenshot (as compressed JPEG)
        log_step("10. Capturing confirmation screenshot...")
        submitted_bytes = await page.screenshot(type="jpeg", quality=50)
        screenshot_submitted_b64 = base64.b64encode(submitted_bytes).decode('utf-8')
        
        log_step("11. Done!")
        print(f"Successfully submitted and captured screenshots for {guest_name}!")
        return {
            "success": True,
            "guestName": guest_name,
            "screenshot_filled": f"data:image/jpeg;base64,{screenshot_filled_b64}",
            "screenshot_submitted": f"data:image/jpeg;base64,{screenshot_submitted_b64}"
        }
        
    except Exception as e:
        err_msg = f"Error: {str(e)}"
        log_step(err_msg)
        print(f"Error filling form for {guest_name}: {e}")
        return {
            "success": False,
            "error": f"Lỗi điền form: {str(e)}",
            "screenshot_filled": "",
            "screenshot_submitted": ""
        }
    finally:
        # Only close context (pages inside it are closed automatically)
        try:
            await context.close()
        except Exception:
            pass

@app.post("/api/submit")
async def submit_to_google_form(request: SubmitRequest):
    async with submit_lock:
        result = await fill_form_playwright(request)
        return result

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8888))
    print(f"Khởi chạy Server tại cổng {port}...")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)

