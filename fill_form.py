import os
import sys
import csv
import re
import time
from datetime import datetime

# Configure console to support Vietnamese output
sys.stdout.reconfigure(encoding='utf-8')

# Define Google Form field mapping (Entry ID -> CSV Column Name / Question Label)
FIELD_MAPPING = {
    "Họ và tên người đăng ký": "178418221",
    "Số điện thoại người đăng ký": "2093418625",
    "Họ và tên khách": "955098140",
    "Năm sinh": "870248713",
    "Mã Căn Hộ": "175253502",
    "Hộ Chiếu_CCCD": "1388064463",
    "VISA": "2009586042",
    "Hạn VISA": "1149566062",
    "Quốc tịch": "1515902134",
    "Thông tin hộ khẩu": "2023500619",
    "Chủ thể": "117977297",      # Dropdown
    "Ngày đến": "1707290555",      # Date
    "Thời gian vào": "1773051864",  # Time
    "Ngày ra": "1028902383",       # Date
    "Cam kết tuân thủ": "1651751105" # Radio/Checkbox: 'Tôi đã đọc và đồng ý'
}

FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSeXLQCQG6siLjJZZ4ZTxVcNpOYymwh5-Yw34HeK45HAp3ohog/viewform"

# Configuration settings
HEADLESS = False       # Set to True to run browser in background
DELAY_BETWEEN_FIELDS = 0.3  # Delay (seconds) between filling each field to look natural
AUTO_SUBMIT = False     # Set to True to automatically click submit. If False, script will fill and wait for you to review.

def parse_date(date_str):
    """
    Parses date string in formats: YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY
    Returns (year, month, day) as strings.
    """
    if not date_str:
        return None
    
    date_str = str(date_str).strip()
    
    # Try YYYY-MM-DD
    match = re.match(r'^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$', date_str)
    if match:
        return match.group(1), match.group(2).zfill(2), match.group(3).zfill(2)
        
    # Try DD/MM/YYYY or DD-MM-YYYY
    match = re.match(r'^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$', date_str)
    if match:
        return match.group(3), match.group(2).zfill(2), match.group(1).zfill(2)
        
    # Try just splitting
    parts = re.split(r'[-/]', date_str)
    if len(parts) == 3:
        if len(parts[0]) == 4:
            return parts[0], parts[1].zfill(2), parts[2].zfill(2)
        elif len(parts[2]) == 4:
            return parts[2], parts[1].zfill(2), parts[0].zfill(2)
            
    print(f"Warning: Không thể định dạng ngày '{date_str}'. Hãy nhập định dạng YYYY-MM-DD hoặc DD/MM/YYYY.")
    return None

def parse_time(time_str):
    """
    Parses time string in formats: HH:MM or HH:MM:SS (24-hour format)
    Returns (hour, minute) as strings.
    """
    if not time_str:
        return None
        
    time_str = str(time_str).strip()
    match = re.match(r'^(\d{1,2}):(\d{2})', time_str)
    if match:
        return match.group(1).zfill(2), match.group(2)
        
    print(f"Warning: Không thể định dạng giờ '{time_str}'. Hãy nhập định dạng HH:MM (ví dụ: 14:30).")
    return None

def fill_form_for_row(page, row_data):
    """
    Fills the Google Form using Playwright based on a single row data dictionary.
    """
    print(f"\n--- Đang điền form cho: {row_data.get('Họ và tên khách', 'Khách hàng mới')} ---")
    
    # 1. Fill basic Text and Paragraph fields
    text_fields = [
        "Họ và tên người đăng ký",
        "Số điện thoại người đăng ký",
        "Họ và tên khách",
        "Năm sinh",
        "Mã Căn Hộ",
        "Hộ Chiếu_CCCD",
        "VISA",
        "Hạn VISA",
        "Quốc tịch",
        "Thông tin hộ khẩu"
    ]
    
    for field in text_fields:
        val = row_data.get(field, "")
        if val is not None and val != "":
            entry_id = FIELD_MAPPING[field]
            print(f"  Điền {field}: {val}")
            
            # Locate container and then locate input/textarea inside it
            container = page.locator(f'div[data-params*="{entry_id}"]')
            
            # Fill the textbox
            input_el = container.locator('input[type="text"], textarea')
            input_el.first.fill(str(val))
            time.sleep(DELAY_BETWEEN_FIELDS)
            
    # 2. Fill Dropdown field (Chủ thể - 117977297)
    subject_val = row_data.get("Chủ thể", "")
    if subject_val:
        entry_id = FIELD_MAPPING["Chủ thể"]
        print(f"  Chọn Chủ thể: {subject_val}")
        container = page.locator(f'div[data-params*="{entry_id}"]')
        
        # Click listbox to open options
        listbox = container.locator('div[role="listbox"]')
        listbox.first.click()
        time.sleep(0.5)
        
        # Click the specific option in the dropdown overlay
        # Since options appear globally, search for option with matching text
        # If Vietnamese vs English text matches partly
        option_text = str(subject_val).strip()
        
        # Handle matching logic
        option_locator = page.locator('div[role="option"]').filter(has_text=option_text).first
        if option_locator.count() > 0:
            option_locator.click()
        else:
            # Fallback to checking by index or contains
            print(f"  Warning: Không tìm thấy tùy chọn '{option_text}' chính xác. Thử tìm kiếm gần đúng...")
            if "Khách đến thăm" in option_text or "Visitor" in option_text:
                page.locator('div[role="option"]').first.click()
            else:
                page.locator('div[role="option"]').nth(1).click()
        time.sleep(DELAY_BETWEEN_FIELDS)

    # 3. Fill Date fields (Ngày đến - 1707290555, Ngày ra - 1028902383)
    for field in ["Ngày đến", "Ngày ra"]:
        date_val = row_data.get(field, "")
        if date_val:
            parsed = parse_date(date_val)
            if parsed:
                year, month, day = parsed
                entry_id = FIELD_MAPPING[field]
                print(f"  Điền {field}: {day}/{month}/{year}")
                container = page.locator(f'div[data-params*="{entry_id}"]')
                
                # Fill day, month, year inputs
                container.locator('input[aria-label="Ngày"], input[aria-label="Day"]').fill(day)
                time.sleep(0.1)
                container.locator('input[aria-label="Tháng"], input[aria-label="Month"]').fill(month)
                time.sleep(0.1)
                container.locator('input[aria-label="Năm"], input[aria-label="Year"]').fill(year)
                time.sleep(DELAY_BETWEEN_FIELDS)

    # 4. Fill Time field (Thời gian vào - 1773051864)
    time_val = row_data.get("Thời gian vào", "")
    if time_val:
        parsed = parse_time(time_val)
        if parsed:
            hour, minute = parsed
            entry_id = FIELD_MAPPING["Thời gian vào"]
            print(f"  Điền Thời gian vào: {hour}:{minute}")
            container = page.locator(f'div[data-params*="{entry_id}"]')
            
            # Fill hour and minute inputs
            container.locator('input[aria-label="Giờ"], input[aria-label="Hour"]').fill(hour)
            time.sleep(0.1)
            container.locator('input[aria-label="Phút"], input[aria-label="Minute"]').fill(minute)
            time.sleep(DELAY_BETWEEN_FIELDS)

    # 5. Fill Radio/Agreement field (Cam kết tuân thủ - 1651751105)
    # The form requires checking 'Tôi đã đọc và đồng ý'
    entry_id = FIELD_MAPPING["Cam kết tuân thủ"]
    container = page.locator(f'div[data-params*="{entry_id}"]')
    print("  Chọn Cam kết tuân thủ: Tôi đã đọc và đồng ý")
    container.locator('div[role="checkbox"], div[role="radio"], span:has-text("Tôi đã đọc và đồng ý")').first.click()
    time.sleep(DELAY_BETWEEN_FIELDS)

    # 6. Handle Submission and Screenshots
    os.makedirs("screenshots", exist_ok=True)
    
    # Sanitize guest name for file naming
    guest_name = row_data.get("Họ và tên khách", "KhachHang")
    clean_name = re.sub(r'[\\/*?:"<>|]', "", str(guest_name)).strip().replace(" ", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Capture screenshot of the filled form (full page to see all inputs)
    screenshot_filled_path = f"screenshots/{clean_name}_{timestamp}_filled.png"
    print(f"  Chụp ảnh màn hình đã điền: {screenshot_filled_path}")
    page.screenshot(path=screenshot_filled_path, full_page=True)
    time.sleep(0.5)

    if AUTO_SUBMIT:
        print("  [Auto] Đang tự động gửi form...")
        submit_btn = page.locator('div[role="button"]:has-text("Gửi"), div[role="button"]:has-text("Submit")').first
        submit_btn.click()
        time.sleep(3)  # Wait for submission confirmation page to load
        print("  Form đã được gửi thành công!")
        
        # Capture screenshot of confirmation screen
        screenshot_submitted_path = f"screenshots/{clean_name}_{timestamp}_submitted.png"
        print(f"  Chụp ảnh màn hình đã gửi: {screenshot_submitted_path}")
        page.screenshot(path=screenshot_submitted_path)
    else:
        print("\n  [Review] Form đã được điền đầy đủ.")
        print("  Hãy kiểm tra trình duyệt và tự bấm nút 'Gửi' nếu thông tin chính xác.")
        input("  Nhấn [ENTER] trong terminal này sau khi đã gửi xong để tiếp tục người tiếp theo...")
        
        # Capture screenshot of current screen after review/manual submit
        screenshot_submitted_path = f"screenshots/{clean_name}_{timestamp}_submitted.png"
        print(f"  Chụp ảnh màn hình sau khi xem xét: {screenshot_submitted_path}")
        page.screenshot(path=screenshot_submitted_path)

def main():
    # Detect the data file
    data_file = None
    if os.path.exists("danh_sach.xlsx"):
        data_file = "danh_sach.xlsx"
    elif os.path.exists("danh_sach.csv"):
        data_file = "danh_sach.csv"
    elif os.path.exists("mau_dang_ky.csv"):
        data_file = "mau_dang_ky.csv"
        print("Lưu ý: Không tìm thấy 'danh_sach.csv' hoặc 'danh_sach.xlsx'. Đang chạy dữ liệu mẫu từ 'mau_dang_ky.csv'...")
    else:
        print("Error: Không tìm thấy tệp dữ liệu nào! Vui lòng tạo tệp 'danh_sach.csv' hoặc chạy 'python create_template.py'.")
        return

    # Try importing Playwright
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Error: Chưa cài đặt Playwright. Vui lòng chạy lệnh:")
        print("  pip install playwright")
        print("  playwright install chromium")
        return

    # Read the data rows
    rows = []
    
    if data_file.endswith(".xlsx"):
        try:
            import pandas as pd
            df = pd.read_excel(data_file)
            # Fill NaN values with empty string
            df = df.fillna("")
            rows = df.to_dict('records')
            print(f"Đọc thành công tệp Excel {data_file} chứa {len(rows)} bản ghi.")
        except ImportError:
            print("Error: Để đọc file Excel (.xlsx), bạn cần cài đặt pandas và openpyxl:")
            print("  pip install pandas openpyxl")
            return
        except Exception as e:
            print(f"Error khi đọc file Excel: {e}")
            return
    else:
        # Read CSV file
        try:
            # Check encoding (UTF-8 with BOM or plain UTF-8 is common in Vietnam)
            encoding = 'utf-8-sig' # handles UTF-8 BOM automatically
            with open(data_file, "r", encoding=encoding) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Strip spaces from keys and values
                    cleaned_row = {k.strip(): (v.strip() if v else "") for k, v in row.items() if k}
                    rows.append(cleaned_row)
            print(f"Đọc thành công tệp CSV {data_file} chứa {len(rows)} bản ghi.")
        except Exception as e:
            print(f"Error khi đọc file CSV: {e}")
            return

    if not rows:
        print("Tệp dữ liệu trống!")
        return

    print("\nKhởi động trình duyệt tự động điền form...")
    with sync_playwright() as p:
        # Launch Chromium. headless=False enables visible browser.
        browser = p.chromium.launch(headless=HEADLESS)
        # Create a new browser context with viewport size
        context = browser.new_context(viewport={"width": 1280, "height": 850})
        page = context.new_page()
        
        for index, row in enumerate(rows):
            print(f"\n================ BẢN GHI {index + 1} / {len(rows)} ================")
            
            # Open form page
            page.goto(FORM_URL)
            page.wait_for_load_state("networkidle")
            
            try:
                fill_form_for_row(page, row)
            except Exception as e:
                print(f"Lỗi khi điền form cho bản ghi {index + 1}: {e}")
                input("Nhấn [ENTER] để bỏ qua và tiếp tục người kế tiếp...")
                
        # Close browser
        print("\nHoàn tất toàn bộ danh sách!")
        browser.close()

if __name__ == "__main__":
    main()
