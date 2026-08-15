import os
os.environ["USE_NNPACK"] = "0"
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"

import io
import sys
import asyncio
import threading

# Fix Playwright subprocess on Windows (ProactorEventLoop required)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import json
import base64
import random
import secrets
import re
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Response, Request, UploadFile, File
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

sys.path.append(os.path.join(os.path.dirname(__file__), "cccd_reader"))
import app as cccd_app
from fastapi import FastAPI, HTTPException, Response, Request, UploadFile, File

ACTIVE_SESSIONS: set = _load_sessions()

def is_authenticated(request: Request) -> bool:
    session_id = request.cookies.get("session_id")
    if session_id and session_id in ACTIVE_SESSIONS:
        return True
    return False

# Pass Level 2 (PRO Mode) Configuration & Session
PRO_PASS = "huyadmin2903"
PRO_SESSION_FILE = os.path.join(os.path.dirname(__file__), ".pro_sessions.json")

def _load_pro_sessions() -> set:
    try:
        if os.path.exists(PRO_SESSION_FILE):
            with open(PRO_SESSION_FILE, "r") as f:
                return set(json.load(f))
    except Exception:
        pass
    return set()

def _save_pro_sessions(sessions: set):
    try:
        with open(PRO_SESSION_FILE, "w") as f:
            json.dump(list(sessions), f)
    except Exception:
        pass

PRO_SESSIONS: set = _load_pro_sessions()

def is_pro_authenticated(request: Request) -> bool:
    pro_id = request.cookies.get("pro_session_id")
    if pro_id and pro_id in PRO_SESSIONS:
        return True
    # If authenticated with admin session, seamlessly authorize PRO capabilities
    if is_authenticated(request):
        return True
    return False

class LoginRequest(BaseModel):
    username: str
    password: str

class VerifyProRequest(BaseModel):
    password: str

class SubmitRequest(BaseModel):
    unitCode: str
    guestId: str
    gender: str
    sharedNation: str = ""
    fullName: str = ""
    birthDate: str = ""
    birthYear: str = ""
    nationality: str = ""
    address: str = ""
    visa: str = ""
    visaExpDate: str = ""

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
    # Pre-warm OCR engine in background thread on startup so first user click is instant
    import threading
    def _warmup():
        try:
            r = cccd_app.get_easy_ocr()
            if r:
                print("[OK] EasyOCR engine ready for instant extraction!")
        except Exception as e:
            print(f"[WARN] Warmup EasyOCR: {e}")
    threading.Thread(target=_warmup, daemon=True).start()
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
        # Auto-grant PRO session on login
        pro_token = secrets.token_urlsafe(32)
        PRO_SESSIONS.add(pro_token)
        _save_pro_sessions(PRO_SESSIONS)
        response.set_cookie(
            key="pro_session_id",
            value=pro_token,
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 365
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

@app.post("/api/verify-pro-pass")
async def verify_pro_pass(data: VerifyProRequest, response: Response):
    if data.password.strip() == PRO_PASS or data.password.strip() == "huyadmin2903":
        token = secrets.token_urlsafe(32)
        PRO_SESSIONS.add(token)
        _save_pro_sessions(PRO_SESSIONS)
        response.set_cookie(
            key="pro_session_id",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 365  # 1 year persistent
        )
        return {"success": True, "token": token}
    raise HTTPException(status_code=401, detail="Mật khẩu cấp 2 không chính xác!")

@app.get("/api/pro-status")
async def get_pro_status(request: Request):
    return {"unlocked": is_pro_authenticated(request)}

_extract_lock = threading.Lock()

def _sync_extract(contents: bytes):
    with _extract_lock:
        import numpy as np
        import cv2
        import time
        t0 = time.time()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            print("[EXTRACT ERROR] Cannot decode image bytes")
            return None
    
    h, w = img.shape[:2]
    print(f"[EXTRACT] 1. Received image shape: {w}x{h} ({len(contents)/1024:.1f} KB)")
    
    # Scale down multi-megapixel camera photos before OCR for high speed
    if max(h, w) > 1200:
        scale = 1200.0 / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        print(f"[EXTRACT] Resized to {img.shape[1]}x{img.shape[0]} in {time.time()-t0:.2f}s")
    
    reader = cccd_app.get_easy_ocr()
    t_orient = time.time()
    oriented_img, rot_deg = cccd_app.smart_orient_document(img, reader)
    print(f"[EXTRACT] 2. Smart oriented (angle {rot_deg}) in {time.time()-t_orient:.2f}s")
    
    t_eng = time.time()
    engine = cccd_app.IntelligentDocumentEngine(reader)
    doc_type, fields, crops, mrz_parsed = engine.process(oriented_img)
    print(f"[EXTRACT] 3. Engine process finished ({doc_type}) in {time.time()-t_eng:.2f}s")
    
    clean_fields = {k: v for k, v in fields.items() if v}
            
    # Generate document thumbnail for UI display
    t_warp = time.time()
    card_img = cccd_app.warp_document(oriented_img, doc_type)
    success, buf = cv2.imencode(".jpg", card_img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    doc_img_b64 = "data:image/jpeg;base64," + base64.b64encode(buf).decode('utf-8') if success else ""
    print(f"[EXTRACT] 4. Warped & encoded thumbnail in {time.time()-t_warp:.2f}s. Total time: {time.time()-t0:.2f}s")

    layout_label_map = {
        'passport': '🛂 Hộ Chiếu Quốc Tế (Passport)',
        'cc_new': '🆔 Thẻ Căn Cước Mới (2024)',
        'cccd_old': '🪪 CCCD Gắn Chip (Trước 2023)'
    }

    return {
        "success": True,
        "layout_label": layout_label_map.get(doc_type, "🛂 Giấy Tờ Hợp Lệ"),
        "doc_type": doc_type,
        "fields": clean_fields,
        "crops": crops,
        "doc_image": doc_img_b64,
        "rotation": rot_deg
    }

@app.post("/api/extract")
async def extract_document(request: Request, image: UploadFile = File(...)):
    if not is_authenticated(request):
        return {"success": False, "detail": "Vui lòng đăng nhập hệ thống!"}
    if not is_pro_authenticated(request):
        return {"success": False, "detail": "Chức năng PRO yêu cầu mật khẩu cấp 2!"}
    
    try:
        contents = await image.read()
        result = await asyncio.to_thread(_sync_extract, contents)
        if result is None:
            return {"success": False, "detail": "Không đọc được file ảnh hoặc định dạng không hỗ trợ!"}
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "detail": f"Lỗi xử lý OCR: {str(e)}"}



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
    
    # 1. Prepare values (Use PRO Real Data if provided, else Realistic Smart Randomization)
    rep_gender = random.choice(["male", "female"])
    rep_name = random.choice(REP_MALE_NAMES) if rep_gender == "male" else random.choice(REP_FEMALE_NAMES)
    
    phone_prefix = random.choice(["09", "03", "07", "08", "05"])
    phone_suffix = "".join(random.choice("0123456789") for _ in range(8))
    rep_phone = phone_prefix + phone_suffix
    
    # Check if the guestId is a Vietnamese CCCD (exactly 12 digits)
    guest_id_clean = "".join(c for c in data.guestId if c.isdigit())
    is_vietnamese_cccd = len(guest_id_clean) == 12 and data.guestId.isdigit()
    gender = data.gender.lower() if data.gender else "female"
    
    # Guest Name
    if data.fullName and data.fullName.strip():
        guest_name = data.fullName.strip().upper()
    else:
        if is_vietnamese_cccd:
            guest_name = random.choice(GUEST_MALE_NAMES[13:]) if gender == "male" else random.choice(GUEST_FEMALE_NAMES[13:])
        else:
            guest_name = random.choice(GUEST_MALE_NAMES[:13]) if gender == "male" else random.choice(GUEST_FEMALE_NAMES[:13])
            
    # Nationality
    if data.nationality and data.nationality.strip():
        nation = data.nationality.strip()
    elif data.sharedNation and data.sharedNation.strip():
        nation = data.sharedNation.strip()
    else:
        nation = "Việt Nam" if is_vietnamese_cccd else random.choice(["Lithuania", "USA", "Đức", "Anh", "Hàn Quốc", "Nga", "Pháp"])
        
    # Year of Birth
    if data.birthYear and data.birthYear.strip():
        birth_year = data.birthYear.strip()
    elif data.birthDate and data.birthDate.strip():
        parts = data.birthDate.strip().split('/')
        birth_year = parts[-1] if len(parts) == 3 else data.birthDate.strip()[-4:]
    else:
        birth_year = str(random.randint(1980, 2003))
        
    # Visa & Visa Expiry
    if is_vietnamese_cccd or nation == "Việt Nam" or "việt nam" in nation.lower():
        visa = "Miễn VISA"
    else:
        visa = data.visa.strip() if (data.visa and data.visa.strip()) else "Du lịch / Tourism"
        
    today = datetime.now()
    checkin_days = random.randint(0, 3)
    checkout_days = checkin_days + random.randint(1, 5)
    
    check_in_date = (today + timedelta(days=checkin_days)).strftime("%Y-%m-%d")
    check_in_time = f"{random.randint(8, 20):02d}:{random.choice([0, 15, 30, 45]):02d}"
    check_out_date = (today + timedelta(days=checkout_days)).strftime("%Y-%m-%d")
    
    visa_exp_date = data.visaExpDate.strip() if (data.visaExpDate and data.visaExpDate.strip()) else (today + timedelta(days=random.randint(30, 90))).strftime("%Y-%m-%d")
    address = data.address.strip() if (data.address and data.address.strip()) else random.choice(ADDRESSES)
    
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
    
    max_retries = 3
    last_err = None
    
    for attempt in range(1, max_retries + 1):
        context = None
        page = None
        browser = None
        
        try:
            if attempt > 1:
                log_step(f"🔄 [{guest_name}] Đang tự động thử lại lần {attempt}/{max_retries}...")
            else:
                log_step(f"1. [{guest_name}] Preparing form page...")
            
            async with async_playwright() as p:
                launch_args = [
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu"
                ] if os.name != 'nt' else []

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
                
                # Block heavy analytics and ads (do not block fonts to prevent Google Form stall)
                async def handle_route(route):
                    try:
                        url = route.request.url.lower()
                        if any(domain in url for domain in [
                            "google-analytics.com", "googletagmanager.com", 
                            "doubleclick.net", "googleadservices.com"
                        ]):
                            await route.abort()
                        else:
                            await route.continue_()
                    except Exception:
                        pass
                await page.route("**/*", handle_route)

                await page.goto(FORM_URL, wait_until="domcontentloaded", timeout=30000)
                
                # 1. Clean & Format Unit Code
                unit_code_clean = row_data["Mã Căn Hộ"].strip().upper()
                m_uc = re.match(r"^([A-Z])[-_\s.]*([0-9]{1,2})[-_\s.]*([0-9]{2})$", unit_code_clean)
                if m_uc:
                    unit_code_clean = f"{m_uc.group(1)}-{int(m_uc.group(2)):02d}.{int(m_uc.group(3)):02d}"
                row_data["Mã Căn Hộ"] = unit_code_clean

                # 2. Fill basic text fields
                log_step(f"2. [{guest_name}] Filling basic text fields...")
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
                    if await container.count() > 0:
                        input_el = container.locator('input[type="text"], textarea')
                        if await input_el.count() > 0:
                            await js_fill(input_el, val)
                            
                # 3. Dropdown: Chủ thể - 117977297 (Bulletproof Double Click + DOM Set)
                log_step(f"3. [{guest_name}] Selecting dropdown subject...")
                container = page.locator('div[data-params*="117977297"]')
                if await container.count() > 0:
                    listbox = container.locator('div[role="listbox"]').first
                    await listbox.click(force=True)
                    await asyncio.sleep(0.15)
                    options = page.locator('div.exportSelectPopup div[role="option"], div.OA06Te div[role="option"], div[role="option"]')
                    target_option = options.filter(has_text="Khách đến thăm")
                    if await target_option.count() > 0:
                        await target_option.first.click(force=True)
                    else:
                        await options.nth(1).click(force=True)
                    await asyncio.sleep(0.1)
                
                # 4. Dates: Ngày đến, Ngày ra
                log_step(f"4. [{guest_name}] Filling check-in/out dates...")
                date_fields = {
                    "Ngày đến": "1707290555",
                    "Ngày ra": "1028902383"
                }
                for label, entry_id in date_fields.items():
                    val = row_data[label]
                    container = page.locator(f'div[data-params*="{entry_id}"]')
                    if await container.count() > 0:
                        await js_fill(container.locator('input[type="date"]'), val)
                    
                # 5. Time: Thời gian vào
                log_step(f"5. [{guest_name}] Filling check-in time...")
                time_val = row_data["Thời gian vào"]
                container = page.locator('div[data-params*="1773051864"]')
                if await container.count() > 0:
                    native_time = container.locator('input[type="time"]')
                    if await native_time.count() > 0:
                        await js_fill(native_time, time_val)
                    else:
                        time_parts = time_val.split(':')
                        if len(time_parts) == 2:
                            hour, minute = time_parts[0], time_parts[1]
                            await js_fill(container.locator('input').nth(0), hour)
                            await js_fill(container.locator('input').nth(1), minute)
                        
                # 6. Agreement checkbox (Verified check state)
                log_step(f"6. [{guest_name}] Checking compliance checkbox...")
                container = page.locator('div[data-params*="1651751105"]')
                if await container.count() > 0:
                    checkbox = container.locator('div[role="checkbox"], div[role="radio"]').first
                    is_checked = await checkbox.get_attribute("aria-checked")
                    if is_checked != "true":
                        await checkbox.click(force=True)
                        await asyncio.sleep(0.08)
                        is_checked = await checkbox.get_attribute("aria-checked")
                        if is_checked != "true":
                            await checkbox.evaluate("el => el.click()")
                
                # 7. Settle and take first screenshot
                log_step(f"7. [{guest_name}] Capturing filled form screenshot...")
                passport_container = page.locator('div[data-params*="1388064463"]')
                if await passport_container.count() > 0:
                    await passport_container.first.evaluate("el => el.scrollIntoView({ behavior: 'instant', block: 'end' })")
                await asyncio.sleep(0.2)

                filled_bytes = await page.screenshot(type="jpeg", quality=35)
                screenshot_filled_b64 = base64.b64encode(filled_bytes).decode('utf-8')
                
                # Click submit
                log_step(f"8. [{guest_name}] Clicking Submit button...")
                submit_btn = page.locator('div[role="button"].Y5sE8d').first
                await submit_btn.click()
                
                # Wait for confirmation page
                log_step(f"9. [{guest_name}] Waiting for confirmation page element...")
                try:
                    await page.locator('.vHW8K, a[href*="viewform"]').first.wait_for(state="visible", timeout=5000)
                except Exception:
                    err_count = await page.locator('div[role="alert"], .iv77ob').count()
                    if err_count > 0:
                        raise Exception("Sai định dạng Mã Căn Hộ hoặc thông tin bị từ chối")
                    else:
                        raise Exception("Hết thời gian chờ trang xác nhận")
                await asyncio.sleep(0.1)
                
                # Take submitted screenshot
                log_step(f"10. [{guest_name}] Capturing confirmation screenshot...")
                submitted_bytes = await page.screenshot(type="jpeg", quality=35)
                screenshot_submitted_b64 = base64.b64encode(submitted_bytes).decode('utf-8')
                
                log_step(f"11. [{guest_name}] Hoàn tất thành công!")
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
            last_err = e
            log_step(f"⚠️ [{guest_name}] Lỗi lần {attempt}/{max_retries}: {str(e)}")
            if attempt < max_retries:
                await asyncio.sleep(0.8)
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
                    
    return {
        "success": False,
        "error": f"Lỗi sau {max_retries} lần thử: {str(last_err)}",
        "screenshot_filled": "",
        "screenshot_submitted": ""
    }


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

submit_semaphore = None

@app.post("/api/submit")
async def submit_to_google_form(submit_request: SubmitRequest, request: Request):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    global submit_semaphore
    if submit_semaphore is None:
        submit_semaphore = asyncio.Semaphore(6)
    async with submit_semaphore:
        result = await fill_form_playwright(submit_request)
        return result


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 1111))
    print(f"Khởi chạy Server tại cổng {port}...")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)


