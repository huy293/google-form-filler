import sys
import os
import random
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding='utf-8')

# Lists of names and addresses for realistic randomization
REP_MALE_NAMES = ["Nguyễn Văn Hùng", "Trần Minh Tuấn", "Lê Hoàng Nam", "Phạm Quốc Bảo", "Nguyễn Hải Dương", "Trần Việt Anh", "Đỗ Minh Đức", "Vũ Huy Hoàng"]
REP_FEMALE_NAMES = ["Nguyễn Thị Mai", "Trần Thu Trang", "Lê Linh Chi", "Phạm Hải Yến", "Nguyễn Khánh An", "Trần Mỹ Linh", "Đỗ Vân Anh"]
GUEST_MALE_NAMES = ["Bennan", "John", "David", "Alex", "Michael", "James"]
GUEST_FEMALE_NAMES = ["Agne", "Amada", "Mary", "Anna", "Linda", "Elizabeth"]
ADDRESSES = ["123 Nguyễn Trãi, Quận 5, TP.HCM", "456 Lê Lợi, Quận 1, TP.HCM"]

def run_sync_test():
    from playwright.sync_api import sync_playwright
    
    rep_name = random.choice(REP_FEMALE_NAMES)
    rep_phone = "0379521619"
    guest_name = "Agne"
    birth_year = "2005"
    unit_code = "A19.999"
    guest_id = "PL0967064"
    nation = "Lithuania"
    visa = "V1234567"
    visa_expiry = "2026-10-10"
    address = random.choice(ADDRESSES)
    check_in_date = "2026-08-10"
    check_in_time = "10:15"
    check_out_date = "2026-08-12"
    
    print("Starting sync Playwright...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("Navigating to form...")
        page.goto("https://docs.google.com/forms/d/e/1FAIpQLSeXLQCQG6siLjJZZ4ZTxVcNpOYymwh5-Yw34HeK45HAp3ohog/viewform", wait_until="load")
        
        print("Filling text inputs...")
        # Text inputs
        fields = {
            "178418221": rep_name,
            "2093418625": rep_phone,
            "955098140": guest_name,
            "870248713": birth_year,
            "175253502": unit_code,
            "1388064463": guest_id,
            "2009586042": visa,
            "1515902134": nation,
            "2023500619": address
        }
        
        for entry_id, val in fields.items():
            container = page.locator(f'div[data-params*="{entry_id}"]')
            container.locator('input[type="text"], textarea').first.fill(str(val))
            
        print("Selecting subject dropdown...")
        # Subject Dropdown: 117977297
        container = page.locator('div[data-params*="117977297"]')
        container.locator('div[role="listbox"]').first.click()
        page.locator('div[role="option"]').filter(has_text="Khách đến thăm").first.click()
        
        print("Filling dates...")
        # Dates: 1707290555, 1028902383, 1149566062
        page.locator('div[data-params*="1707290555"]').locator('input[type="date"]').fill(check_in_date)
        page.locator('div[data-params*="1028902383"]').locator('input[type="date"]').fill(check_out_date)
        page.locator('div[data-params*="1149566062"]').locator('input[type="date"]').fill(visa_expiry)
        
        print("Filling time...")
        # Time: 1773051864
        t_container = page.locator('div[data-params*="1773051864"]')
        t_container.locator('input[type="text"]').nth(0).fill("10")
        t_container.locator('input[type="text"]').nth(1).fill("15")
        
        print("Checking agreement...")
        # Checkbox: 1651751105
        page.locator('div[data-params*="1651751105"]').locator('div[role="checkbox"], div[role="radio"]').first.click()
        
        print("Taking filled screenshot...")
        page.screenshot(path="scratch/filled_test.png", full_page=True)
        
        print("Submitting...")
        page.locator('div[role="button"]:has-text("Gửi"), div[role="button"]:has-text("Submit")').first.click()
        page.wait_for_load_state("networkidle")
        
        print("Taking submitted screenshot...")
        page.screenshot(path="scratch/submitted_test.png")
        
        print("Completed successfully!")
        browser.close()

if __name__ == "__main__":
    run_sync_test()
