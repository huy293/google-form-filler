# Công cụ Tự Động Điền Google Form (Đăng ký thông tin sảnh)

Chào mừng bạn! Đây là công cụ hỗ trợ tự động điền nhanh và điền hàng loạt thông tin vào Google Form **ĐĂNG KÝ THÔNG TIN SẢNH**.

Công cụ này đã được nâng cấp lên phiên bản **Web App di động (Mobile-friendly)** để bạn dễ dàng sử dụng trên điện thoại, đồng thời vẫn giữ lại các script chạy bằng máy tính.

---

## 🚀 Các cách sử dụng công cụ

### 🔹 Cách 1: Sử dụng qua Web App trên điện thoại hoặc máy tính (Khuyên dùng)
Trang web có giao diện tối ưu di động (Glassmorphism), cho phép bạn nhập nhanh một khách hoặc tải lên tệp danh sách để tự động gửi hàng loạt.

#### Chạy cục bộ (Local):
1. Cài đặt các thư viện cần thiết:
   ```bash
   pip install -r requirements.txt
   ```
2. Chạy server FastAPI:
   ```bash
   python main.py
   ```
3. Mở trình duyệt trên máy tính truy cập: [http://localhost:8080](http://localhost:8080)
4. **Truy cập từ điện thoại qua mạng Wifi**:
   - Tìm địa chỉ IP nội bộ của máy tính bạn (ví dụ: `192.168.1.15` bằng cách gõ `ipconfig` trong terminal).
   - Trên điện thoại di động (kết nối cùng Wifi), mở trình duyệt và truy cập: `http://192.168.1.15:8080`. Bạn đã có thể nhập và gửi form trực tiếp từ điện thoại!

---

## ☁️ Hướng dẫn đưa lên Internet miễn phí (Deploy to Web)

Để làm việc mọi lúc mọi nơi trên điện thoại mà không cần bật máy tính, bạn có thể đưa ứng dụng này lên các dịch vụ đám mây miễn phí như **Render.com**.

### Các bước triển khai qua Render.com:
1. **Bước 1**: Đăng tải mã nguồn này lên **GitHub** của bạn (Tạo một Repo mới và upload toàn bộ các file trong thư mục này lên).
2. **Bước 2**: Đăng ký/Đăng nhập tài khoản miễn phí trên [Render.com](https://render.com).
3. **Bước 3**: Trên trang Dashboard của Render, click **New +** -> Chọn **Web Service**.
4. **Bước 4**: Liên kết với tài khoản GitHub của bạn và chọn Repo vừa upload.
5. **Bước 5**: Cấu hình các thông số sau:
   - **Runtime**: Chọn `Python` (hoặc `Docker` vì dự án đã có sẵn file `Dockerfile`).
   - **Build Command**: `pip install -r requirements.txt` (nếu chọn Runtime là Python).
   - **Start Command**: `python main.py` (nếu chọn Runtime là Python).
   - **Instance Type**: Chọn gói **Free** (Miễn phí).
6. **Bước 6**: Click **Deploy Web Service**. Sau khoảng 2-3 phút, Render sẽ cấp cho bạn một đường link HTTPS công khai (ví dụ: `https://ten-ung-dung.onrender.com`). Bạn có thể lưu link này vào điện thoại để mở ra và dùng bất cứ lúc nào!

---

### 🔹 Cách 2: Chạy tự động điền qua Playwright trên máy tính
Mở trình duyệt ảo Chromium tự động điền trực quan:
1. Cài đặt trình duyệt tự động điền:
   ```bash
   playwright install chromium
   ```
2. Chạy script:
   ```bash
   python fill_form.py
   ```
*(Xem hướng dẫn chỉnh sửa file `mau_dang_ky.csv` để chuẩn bị dữ liệu trong file này).*

---

### 🔹 Cách 3: Tạo trang HTML liên kết điền sẵn (Pre-filled Link)
Tạo tệp HTML chứa các nút bấm điền sẵn thông tin:
1. Chạy script:
   ```bash
   python generate_links.py
   ```
2. Mở file [`danh_sach_lien_ket.html`](file:///C:/Users/luuhu/.gemini/antigravity/scratch/google-form-filler/danh_sach_lien_ket.html) trong trình duyệt máy tính của bạn để click mở nhanh form điền sẵn.

---

## 📂 Danh sách các file trong dự án

1. [`main.py`](file:///C:/Users/luuhu/.gemini/antigravity/scratch/google-form-filler/main.py): Backend server FastAPI xử lý API gửi form trực tiếp và đọc file.
2. [`static/index.html`](file:///C:/Users/luuhu/.gemini/antigravity/scratch/google-form-filler/static/index.html): Giao diện Web di động (UI Glassmorphism đẹp mắt).
3. [`Dockerfile`](file:///C:/Users/luuhu/.gemini/antigravity/scratch/google-form-filler/Dockerfile): File Docker dùng cho việc deploy lên Render / Hugging Face.
4. [`fill_form.py`](file:///C:/Users/luuhu/.gemini/antigravity/scratch/google-form-filler/fill_form.py): Script tự động điền qua Playwright trên máy tính.
5. [`generate_links.py`](file:///C:/Users/luuhu/.gemini/antigravity/scratch/google-form-filler/generate_links.py): Script sinh trang web HTML chứa link điền sẵn.
6. [`mau_dang_ky.csv`](file:///C:/Users/luuhu/.gemini/antigravity/scratch/google-form-filler/mau_dang_ky.csv): Dữ liệu mẫu ban đầu để thử nghiệm.
7. [`requirements.txt`](file:///C:/Users/luuhu/.gemini/antigravity/scratch/google-form-filler/requirements.txt): Khai báo các thư viện Python cần cài đặt.
