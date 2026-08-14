import asyncio
import time
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8')

async def main():
    print("=== BẮT ĐẦU CHẠY THỬ NGHIỆM ĐĂNG KÝ 4 KHÁCH / 1 PHÒNG TỐI ƯU ===")
    async with async_playwright() as p:
        # Launch browser in non-headless mode (headless=False) so you can watch it live on screen
        print("\n[HỆ THỐNG]: Đang khởi chạy trình duyệt ảo (Headless=False)...")
        browser = await p.chromium.launch(headless=False, slow_mo=100)
        page = await browser.new_page()
        
        # Listen to browser console messages to capture live logs from the web console!
        def on_console(msg):
            # Print server logs and browser console messages clearly
            if "1." in msg.text or "2." in msg.text or "3." in msg.text or "4." in msg.text or "Done!" in msg.text or "Successfully" in msg.text:
                print(f"   [Live Server Log]: {msg.text}")
            elif "Error" in msg.text or "Lỗi" in msg.text:
                print(f"   [Live Server Error]: {msg.text}")
            else:
                # Normal web logs (optional, uncomment to debug UI)
                # print(f"[BROWSER CONSOLE] {msg.type.upper()}: {msg.text}")
                pass
        page.on("console", on_console)
        
        print("\n1. Đang mở trang web Render...")
        start_time = time.time()
        try:
            await page.goto("https://google-form-filler-lydg.onrender.com/", wait_until="load", timeout=40000)
            print(f"-> Trang web Render tải xong sau: {time.time() - start_time:.2f} giây")
        except Exception as e:
            print(f"-> Lỗi tải trang Render: {e}")
            await browser.close()
            return
            
        # Fill data into the Render web page inputs
        print("\n2. Điền thông tin Mã căn hộ và tạo 4 khách...")
        await page.locator("#unitCode").fill("A-12.34")
        
        # Click add guest button 3 times to make 4 guest inputs total
        for _ in range(3):
            await page.locator(".btn-add-guest").click()
            await asyncio.sleep(0.1)
            
        passports = ["123123123123", "C1234567", "312123123123", "A9876543"]
        print("-> Đang điền 4 số Hộ chiếu/CCCD...")
        for idx, passport in enumerate(passports):
            await page.locator(".guest-passport").nth(idx).fill(passport)
            
        # Click the submit button on the webpage
        print("\n3. Click nút 'Bắt Đầu Đăng Ký & Chụp Ảnh'...")
        submit_start = time.time()
        await page.locator("#btnSubmit").click()
        
        # Wait for all 4 badges to display "Thành công" or "Thất bại"
        print("4. Đang chờ kết quả hiển thị trên màn hình. Xem log trực tiếp bên dưới:")
        
        for i in range(4):
            badge = page.locator(f"#statusBadge-{i}")
            try:
                # Wait up to 60 seconds per guest registration progress
                await page.wait_for_function(
                    f"el => el.textContent.trim() === 'Thành công' || el.textContent.trim() === 'Thất bại'",
                    arg=await badge.element_handle(),
                    timeout=80000
                )
                status = await badge.text_content()
                print(f"   -> Khách #{i+1} ({passports[i]}): {status.strip()}")
            except Exception as e:
                print(f"   -> Khách #{i+1} ({passports[i]}): Timeout/Lỗi: {e}")
                
        total_time = time.time() - submit_start
        print(f"\n=============================================")
        print(f"=== ĐĂNG KÝ 4 KHÁCH HOÀN TẤT TRONG: {total_time:.2f} GIÂY ===")
        print(f"=============================================")
        
        # Wait for 15 seconds so you can watch the final screenshot grid results
        print("\n[HỆ THỐNG]: Đang giữ trình duyệt mở trong 15 giây để bạn theo dõi kết quả...")
        await asyncio.sleep(15)
        
        # Close browser
        await browser.close()
        print("\n=== KẾT THÚC QUÁ TRÌNH KIỂM THỬ THỰC TẾ ===")

if __name__ == "__main__":
    asyncio.run(main())
