import sys
sys.stdout.reconfigure(encoding='utf-8')
import csv

# Define the fields matching the form questions
headers = [
    "Họ và tên người đăng ký",
    "Số điện thoại người đăng ký",
    "Họ và tên khách",
    "Năm sinh",
    "Mã Căn Hộ",
    "Hộ Chiếu_CCCD",
    "VISA",
    "Hạn VISA",
    "Quốc tịch",
    "Thông tin hộ khẩu",
    "Chủ thể", # 'Khách đến thăm/ Visitors' hoặc 'Khách thuê mới chuyển đến...'
    "Ngày đến", # YYYY-MM-DD
    "Thời gian vào", # HH:MM (24h)
    "Ngày ra", # YYYY-MM-DD
    "Cam kết tuân thủ" # 'Tôi đã đọc và đồng ý' hoặc để trống (script sẽ tự động check)
]

# Real guest examples from the screenshots
rows = [
    [
        "Nguyễn Văn A",
        "0379521619",
        "Bennan",
        "2008",
        "A8.10",
        "PL4186782",
        "",
        "",
        "Nước ngoài",
        "Rivergate Residence, Quận 4",
        "Khách đến thăm/ Visitors",
        "2026-08-11",
        "19:48",
        "2026-08-15",
        "Tôi đã đọc và đồng ý"
    ],
    [
        "Nguyễn Văn A",
        "0379521619",
        "Agne",
        "2005",
        "A8.10",
        "PL0967064",
        "",
        "",
        "Nước ngoài",
        "Rivergate Residence, Quận 4",
        "Khách đến thăm/ Visitors",
        "2026-08-11",
        "19:50",
        "2026-08-15",
        "Tôi đã đọc và đồng ý"
    ],
    [
        "Nguyễn Văn A",
        "0379521619",
        "Amada",
        "2007",
        "A8.10",
        "PH2509507",
        "",
        "",
        "Nước ngoài",
        "Rivergate Residence, Quận 4",
        "Khách đến thăm/ Visitors",
        "2026-08-11",
        "19:51",
        "2026-08-15",
        "Tôi đã đọc và đồng ý"
    ]
]

with open("mau_dang_ky.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow(headers)
    writer.writerows(rows)

print("Đã cập nhật tệp mau_dang_ky.csv với 3 khách hàng ví dụ thành công!")
