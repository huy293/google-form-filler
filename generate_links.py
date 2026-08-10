import os
import sys
import csv
import urllib.parse

# Configure console to support Vietnamese output
sys.stdout.reconfigure(encoding='utf-8')

# Define Google Form URL and field mapping
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSeXLQCQG6siLjJZZ4ZTxVcNpOYymwh5-Yw34HeK45HAp3ohog/viewform"

FIELD_MAPPING = {
    "Họ và tên người đăng ký": "entry.178418221",
    "Số điện thoại người đăng ký": "entry.2093418625",
    "Họ và tên khách": "entry.955098140",
    "Năm sinh": "entry.870248713",
    "Mã Căn Hộ": "entry.175253502",
    "Hộ Chiếu_CCCD": "entry.1388064463",
    "VISA": "entry.2009586042",
    "Hạn VISA": "entry.1149566062",
    "Quốc tịch": "entry.1515902134",
    "Thông tin hộ khẩu": "entry.2023500619",
    "Chủ thể": "entry.117977297",
    "Ngày đến": "entry.1707290555",
    "Thời gian vào": "entry.1773051864",
    "Ngày ra": "entry.1028902383",
    "Cam kết tuân thủ": "entry.1651751105"
}

def generate_url(row_data):
    """
    Generates a prefilled Google Form URL from row data.
    """
    params = {}
    for col, entry_id in FIELD_MAPPING.items():
        val = row_data.get(col, "")
        if val is not None and val != "":
            # Handle date fields (Google prefilled link accepts YYYY-MM-DD)
            if col in ["Ngày đến", "Ngày ra", "Hạn VISA"]:
                val = str(val).strip()
            params[entry_id] = str(val).strip()
            
    # Auto fill agreement if not filled
    if FIELD_MAPPING["Cam kết tuân thủ"] not in params:
        params[FIELD_MAPPING["Cam kết tuân thủ"]] = "Tôi đã đọc và đồng ý"
        
    query_string = urllib.parse.urlencode(params)
    return f"{FORM_URL}?{query_string}"

def main():
    # Detect the data file
    data_file = None
    if os.path.exists("danh_sach.xlsx"):
        data_file = "danh_sach.xlsx"
    elif os.path.exists("danh_sach.csv"):
        data_file = "danh_sach.csv"
    elif os.path.exists("mau_dang_ky.csv"):
        data_file = "mau_dang_ky.csv"
    else:
        print("Error: Không tìm thấy tệp dữ liệu!")
        return

    # Read data
    rows = []
    if data_file.endswith(".xlsx"):
        try:
            import pandas as pd
            df = pd.read_excel(data_file)
            df = df.fillna("")
            rows = df.to_dict('records')
        except Exception as e:
            print(f"Error khi đọc Excel: {e}")
            return
    else:
        try:
            with open(data_file, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cleaned_row = {k.strip(): (v.strip() if v else "") for k, v in row.items() if k}
                    rows.append(cleaned_row)
        except Exception as e:
            print(f"Error khi đọc CSV: {e}")
            return

    if not rows:
        print("Tệp dữ liệu trống!")
        return

    print(f"Đang tạo link điền sẵn cho {len(rows)} khách hàng...")

    # Generate HTML content
    html_content = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Danh Sách Đường Link Điền Sẵn Google Form</title>
    <style>
        :root {
            --primary: #5746e3;
            --primary-hover: #4535c4;
            --bg: #f8f9fc;
            --card-bg: #ffffff;
            --text: #2d3748;
            --text-muted: #718096;
            --border: #e2e8f0;
            --success: #48bb78;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 40px 20px;
        }
        .container {
            max-width: 1000px;
            margin: 0 auto;
        }
        h1 {
            color: var(--primary);
            text-align: center;
            margin-bottom: 10px;
        }
        .subtitle {
            text-align: center;
            color: var(--text-muted);
            margin-bottom: 40px;
        }
        .table-container {
            background-color: var(--card-bg);
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            overflow: hidden;
            border: 1px solid var(--border);
        }
        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }
        th {
            background-color: #edf2f7;
            color: var(--text);
            padding: 16px;
            font-weight: 600;
            border-bottom: 2px solid var(--border);
        }
        td {
            padding: 16px;
            border-bottom: 1px solid var(--border);
            font-size: 15px;
        }
        tr:hover {
            background-color: #f7fafc;
        }
        .btn-fill {
            display: inline-block;
            background-color: var(--primary);
            color: white;
            padding: 8px 16px;
            border-radius: 6px;
            text-decoration: none;
            font-weight: 500;
            font-size: 14px;
            transition: all 0.2s;
            border: 1px solid transparent;
        }
        .btn-fill:hover {
            background-color: var(--primary-hover);
            transform: translateY(-1px);
        }
        .btn-fill:active {
            transform: translateY(0);
        }
        .tag-sub {
            font-size: 12px;
            padding: 4px 8px;
            border-radius: 20px;
            background-color: #e2e8f0;
            color: var(--text-muted);
            font-weight: 500;
        }
        .footer {
            margin-top: 30px;
            text-align: center;
            font-size: 13px;
            color: var(--text-muted);
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>ĐĂNG KÝ THÔNG TIN SẢNH</h1>
        <p class="subtitle">Bảng quản lý danh sách và đường liên kết điền sẵn thông tin</p>
        
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th style="width: 5%;">STT</th>
                        <th style="width: 25%;">Họ và tên khách</th>
                        <th style="width: 15%;">Số ĐT / Mã Căn Hộ</th>
                        <th style="width: 20%;">Thời gian vào</th>
                        <th style="width: 20%;">Chủ thể</th>
                        <th style="width: 15%; text-align: center;">Hành động</th>
                    </tr>
                </thead>
                <tbody>
"""

    for i, row in enumerate(rows):
        prefilled_url = generate_url(row)
        stt = i + 1
        name = row.get("Họ và tên khách", "N/A")
        phone = row.get("Số điện thoại người đăng ký", "")
        unit = row.get("Mã Căn Hộ", "")
        time_in = row.get("Thời gian vào", "")
        date_in = row.get("Ngày đến", "")
        subject = row.get("Chủ thể", "")
        
        contact_info = f"{phone}" if phone else ""
        if unit:
            contact_info += f" ({unit})" if contact_info else unit
            
        time_info = f"{time_in} ngày {date_in}" if time_in else date_in

        html_content += f"""
                    <tr>
                        <td>{stt}</td>
                        <td><strong>{name}</strong></td>
                        <td>{contact_info}</td>
                        <td>{time_info}</td>
                        <td><span class="tag-sub">{subject}</span></td>
                        <td style="text-align: center;">
                            <a href="{prefilled_url}" target="_blank" class="btn-fill">Mở Form điền sẵn</a>
                        </td>
                    </tr>
"""

    html_content += """
                </tbody>
            </table>
        </div>
        <div class="footer">
            Công cụ được tạo tự động để hỗ trợ điền nhanh thông tin Google Form.
        </div>
    </div>
</body>
</html>
"""

    output_file = "danh_sach_lien_ket.html"
    with open(output_file, "w", encoding="utf-8") as outf:
        outf.write(html_content)
        
    print(f"Đã tạo file HTML danh sách liên kết thành công: {output_file}")
    print("Bạn có thể mở tệp này bằng bất kỳ trình duyệt nào và click vào các nút để mở form điền sẵn!")

if __name__ == "__main__":
    main()
