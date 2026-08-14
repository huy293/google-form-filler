import os
import io
import sys
import asyncio

# Fix Playwright subprocess on Windows (ProactorEventLoop required)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import json
import base64
import random
import secrets
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Response, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from playwright.async_api import async_playwright
from contextlib import asynccontextmanager

# Configure console to support Vietnamese output
sys.stdout.reconfigure(encoding='utf-8')

# Authentication credentials & persistent session storage
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
VALID_PASSWORDS = {os.environ.get("ADMIN_PASS", "admin"), "admin", "admin123", "123456", "rivergate123"}

SESSION_FILE = os.path.join(os.path.dirname(__file__), ".sessions.json")

def _load_sessions() -> set:
    try:
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, "r") as f:
                return set(json.load(f))
    except Exception:
        pass
    return set()

def _save_sessions(sessions: set):
    try:
        with open(SESSION_FILE, "w") as f:
            json.dump(list(sessions), f)
    except Exception:
        pass

ACTIVE_SESSIONS: set = _load_sessions()

def is_authenticated(request: Request) -> bool:
    session_id = request.cookies.get("session_id")
    if session_id and session_id in ACTIVE_SESSIONS:
        return True
    return False

class LoginRequest(BaseModel):
    username: str
    password: str

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

submit_lock = None

# Image cache to serve real URLs for mobile download compatibility
IMAGE_CACHE = {}
IMAGE_CACHE_KEYS = []
MAX_CACHE_SIZE = 100

def cache_image(img_b64: str) -> str:
    if not img_b64:
        return ""
    import uuid
    img_id = str(uuid.uuid4())
    try:
        # Convert base64 data URI (if present) or raw base64 back to binary bytes
        if "," in img_b64:
            base64_data = img_b64.split(",")[1]
        else:
            base64_data = img_b64
        img_bytes = base64.b64decode(base64_data)
        IMAGE_CACHE[img_id] = img_bytes
        IMAGE_CACHE_KEYS.append(img_id)
        
        # Prune old cache items
        while len(IMAGE_CACHE_KEYS) > MAX_CACHE_SIZE:
            old_key = IMAGE_CACHE_KEYS.pop(0)
            IMAGE_CACHE.pop(old_key, None)
    except Exception as e:
        print(f"Error caching image: {e}")
        return ""
    return img_id

# Global browser singleton for speed and low RAM usage on Render
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSeXLQCQG6siLjJZZ4ZTxVcNpOYymwh5-Yw34HeK45HAp3ohog/viewform"
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSeXLQCQG6siLjJZZ4ZTxVcNpOYymwh5-Yw34HeK45HAp3ohog/viewform"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fully stateless container, no pre-warming to keep initial RAM footprint extremely low
    yield

app = FastAPI(title="Google Form Auto-Filler Web API", lifespan=lifespan)

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    if not is_authenticated(request):
        login_path = os.path.join(os.path.dirname(__file__), "static", "fake502.html")
        if os.path.exists(login_path):
            with open(login_path, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read(), status_code=200)
        return HTMLResponse(content="<h1>502 Bad Gateway</h1>", status_code=200)
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h3>Error: static/index.html not found!</h3>"

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/api/login")
async def api_login(data: LoginRequest, response: Response):
    if data.username == ADMIN_USER and data.password in VALID_PASSWORDS:
        session_id = secrets.token_urlsafe(32)
        ACTIVE_SESSIONS.add(session_id)
        _save_sessions(ACTIVE_SESSIONS)
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 30  # 30 days persistent
        )
        return {"success": True}
    raise HTTPException(status_code=401, detail="Sai tài khoản hoặc mật khẩu!")

@app.post("/api/logout")
async def api_logout(request: Request, response: Response):
    session_id = request.cookies.get("session_id")
    if session_id:
        ACTIVE_SESSIONS.discard(session_id)
        _save_sessions(ACTIVE_SESSIONS)
    response.delete_cookie("session_id")
    return {"success": True}

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

async def js_fill(locator, value):
    await locator.first.evaluate("""
        (el, val) => {
            el.value = val;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            el.dispatchEvent(new Event('blur', { bubbles: true }));
        }
    """, str(value))

async def fill_form_playwright(data: SubmitRequest):
    # Reset log array for this specific request immediately
    global RUNNING_LOGS
    RUNNING_LOGS = []
    
    # 1. Generate random values
    rep_gender = random.choice(["male", "female"])
    rep_name = random.choice(REP_MALE_NAMES) if rep_gender == "male" else random.choice(REP_FEMALE_NAMES)
    
    phone_prefix = random.choice(["09", "03", "07", "08", "05"])
    phone_suffix = "".join(random.choice("0123456789") for _ in range(8))
    rep_phone = phone_prefix + phone_suffix
    
    # Check if the guestId is a Vietnamese CCCD (exactly 12 digits)
    guest_id_clean = "".join(c for c in data.guestId if c.isdigit())
    is_vietnamese_cccd = len(guest_id_clean) == 12 and data.guestId.isdigit()
    
    is_foreign = not is_vietnamese_cccd
    gender = data.gender.lower()
    
    if is_foreign:
        guest_name = random.choice(GUEST_MALE_NAMES[:13]) if gender == "male" else random.choice(GUEST_FEMALE_NAMES[:13])
        nation = random.choice(["Lithuania", "USA", "Đức", "Anh", "Hàn Quốc", "Nga", "Pháp"])
    else:
        guest_name = random.choice(GUEST_MALE_NAMES[13:]) if gender == "male" else random.choice(GUEST_FEMALE_NAMES[13:])
        nation = "Việt Nam"
        
    birth_year = random.randint(1980, 2003)
    visa = "Miễn VISA" if is_vietnamese_cccd else "Du lịch / Tourism"
    
    today = datetime.now()
    checkin_days = random.randint(0, 3)
    checkout_days = checkin_days + random.randint(1, 5)
    
    check_in_date = (today + timedelta(days=checkin_days)).strftime("%Y-%m-%d")
    check_in_time = f"{random.randint(8, 20):02d}:{random.choice([0, 15, 30, 45]):02d}"
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
    
    log_step("1. Preparing form page...")
    
    context = None
    page = None
    browser = None
    
    try:
        async with async_playwright() as p:
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
            browser = await p.chromium.launch(
                headless=is_headless,
                args=launch_args
            )
            
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 393, "height": 851},
                is_mobile=True,
                has_touch=True
            )
            # Bypassing webdriver detection
            await context.add_init_script("delete navigator.__proto__.webdriver;")
            
            page = await context.new_page()
            
            # Block fonts, analytics, and tracking scripts
            async def handle_route(route):
                url = route.request.url.lower()
                resource_type = route.request.resource_type
                if any(domain in url for domain in [
                    "google-analytics.com", "googletagmanager.com", "analytics", 
                    "collect?", "doubleclick.net", "googleadservices.com",
                    "fonts.googleapis.com", "fonts.gstatic.com"
                ]) or resource_type in ["font"]:
                    await route.abort()
                else:
                    await route.continue_()
            await page.route("**/*", handle_route)
            
            await page.goto(FORM_URL, wait_until="domcontentloaded", timeout=18000)
            
            # 1. Fill basic text fields
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
                        await js_fill(input_el, val)
                        
            # Dropdown: Chủ thể - 117977297
            log_step("3. Clicking dropdown subject...")
            container = page.locator('div[data-params*="117977297"]')
            await container.locator('div[role="listbox"]').first.click(force=True)
            await asyncio.sleep(0.3)
            options = page.locator('div.exportSelectPopup div[role="option"], div.OA06Te div[role="option"]')
            if await options.count() == 0:
                options = page.locator('div[role="option"]')
            await options.first.wait_for(state="visible", timeout=5000)
            target_option = options.filter(has_text="Khách đến thăm")
            if await target_option.count() > 0:
                await target_option.first.evaluate("el => el.click()")
            else:
                await options.nth(1).evaluate("el => el.click()")
            await asyncio.sleep(0.3)
            
            # Dates: Ngày đến, Ngày ra
            log_step("4. Filling check-in/out dates...")
            date_fields = {
                "Ngày đến": "1707290555",
                "Ngày ra": "1028902383"
            }
            for label, entry_id in date_fields.items():
                val = row_data[label]
                container = page.locator(f'div[data-params*="{entry_id}"]')
                await js_fill(container.locator('input[type="date"]'), val)
                
            # Time: Thời gian vào
            log_step("5. Filling check-in time...")
            time_val = row_data["Thời gian vào"]
            container = page.locator('div[data-params*="1773051864"]')
            native_time = container.locator('input[type="time"]')
            if await native_time.count() > 0:
                await js_fill(native_time, time_val)
            else:
                time_parts = time_val.split(':')
                if len(time_parts) == 2:
                    hour, minute = time_parts[0], time_parts[1]
                    await js_fill(container.locator('input').nth(0), hour)
                    await js_fill(container.locator('input').nth(1), minute)
                    
            # Agreement checkbox
            log_step("6. Checking compliance checkbox...")
            container = page.locator('div[data-params*="1651751105"]')
            await container.locator('div[role="checkbox"], div[role="radio"]').first.click(force=True)
            await asyncio.sleep(0.05)
            
            # Settle and take first screenshot
            log_step("7. Capturing filled form screenshot (scrolled to passport)...")
            passport_container = page.locator('div[data-params*="1388064463"]')
            if await passport_container.count() > 0:
                await passport_container.first.evaluate("el => el.scrollIntoView({ behavior: 'instant', block: 'end' })")
            await asyncio.sleep(0.3)
            filled_bytes = await page.screenshot(type="jpeg", quality=35)
            screenshot_filled_b64 = base64.b64encode(filled_bytes).decode('utf-8')
            
            # Click submit
            log_step("8. Clicking Submit button...")
            submit_btn = page.locator('div[role="button"].Y5sE8d').first
            await submit_btn.click()
            
            # Wait for confirmation page
            log_step("9. Waiting for confirmation page element...")
            try:
                await page.locator('.vHW8K, a[href*="viewform"]').first.wait_for(state="visible", timeout=4000)
            except Exception:
                err_count = await page.locator('div[role="alert"], .iv77ob').count()
                if err_count > 0:
                    raise Exception("Sai định dạng Mã Căn Hộ hoặc thông tin nhập vào bị Google Form từ chối (Vui lòng điền đúng mẫu A-12.34)")
                else:
                    raise Exception("Không nhận được trang xác nhận gửi thành công từ Google Form (Hết thời gian chờ)")
            await asyncio.sleep(0.1)
            
            # Take submitted screenshot
            log_step("10. Capturing confirmation screenshot...")
            submitted_bytes = await page.screenshot(type="jpeg", quality=35)
            screenshot_submitted_b64 = base64.b64encode(submitted_bytes).decode('utf-8')
            
            log_step("11. Done!")
            print(f"Successfully submitted and captured screenshots for {guest_name}!")
            
            img_filled_id = cache_image(screenshot_filled_b64)
            img_submitted_id = cache_image(screenshot_submitted_b64)
            
            return {
                "success": True,
                "guestName": guest_name,
                "screenshot_filled": f"/api/image/{img_filled_id}" if img_filled_id else "",
                "screenshot_submitted": f"/api/image/{img_submitted_id}" if img_submitted_id else ""
            }
            
    except Exception as e:
        err_msg = f"Error: {str(e)}"
        log_step(err_msg)
        print(f"Error filling form for {guest_name}: {e}")
        try:
            if page:
                await page.evaluate("window.scrollTo(0, 0);")
                await asyncio.sleep(0.1)
                err_bytes = await page.screenshot(type="jpeg", quality=30)
                err_b64 = base64.b64encode(err_bytes).decode('utf-8')
            else:
                err_b64 = ""
        except Exception:
            err_b64 = ""
        err_img_id = cache_image(err_b64) if err_b64 else ""
        return {
            "success": False,
            "error": f"Lỗi điền form: {str(e)}",
            "screenshot_filled": f"/api/image/{err_img_id}" if err_img_id else "",
            "screenshot_submitted": ""
        }
    finally:
        if page:
            try:
                await page.close()
            except Exception:
                pass
        if context:
            try:
                await context.close()
            except Exception:
                pass
        if browser:
            try:
                await browser.close()
            except Exception:
                pass

@app.get("/api/image/{img_id}")
async def serve_cached_image(img_id: str):
    if img_id not in IMAGE_CACHE:
        raise HTTPException(status_code=404, detail="Image not found or expired")
    return Response(
        content=IMAGE_CACHE[img_id],
        media_type="image/jpeg",
        headers={
            "Content-Disposition": f"attachment; filename=screenshot_{img_id}.jpg"
        }
    )

@app.post("/api/submit")
async def submit_to_google_form(submit_request: SubmitRequest, request: Request):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    global submit_lock
    if submit_lock is None:
        submit_lock = asyncio.Lock()
    async with submit_lock:
        result = await fill_form_playwright(submit_request)
        return result

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8888))
    print(f"Khởi chạy Server tại cổng {port}...")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)

