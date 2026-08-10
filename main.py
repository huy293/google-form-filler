import os
import io
import csv
import sys
import requests
import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

# Set output encoding to support Vietnamese logging
sys.stdout.reconfigure(encoding='utf-8')

app = FastAPI(title="Google Form Auto-Filler Web API")

# Google Form Config
FORM_POST_URL = "https://docs.google.com/forms/d/e/1FAIpQLSeXLQCQG6siLjJZZ4ZTxVcNpOYymwh5-Yw34HeK45HAp3ohog/formResponse"

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

class GuestSubmission(BaseModel):
    Họ_và_tên_người_đăng_ký: Optional[str] = None
    Số_điện_thoại_người_đăng_ký: Optional[str] = None
    Họ_và_tên_khách: Optional[str] = None
    Năm_sinh: Optional[str] = None
    Mã_Căn_Hộ: Optional[str] = None
    Hộ_Chiếu_CCCD: Optional[str] = None
    VISA: Optional[str] = ""
    Hạn_VISA: Optional[str] = ""
    Quốc_tịch: Optional[str] = None
    Thông_tin_hộ_khẩu: Optional[str] = None
    Chủ_thể: Optional[str] = None
    Ngày_đến: Optional[str] = None
    Thời_gian_vào: Optional[str] = None
    Ngày_ra: Optional[str] = None
    Cam_kết_tuân_thủ: Optional[str] = "Tôi đã đọc và đồng ý"

    # Support dictionary indexing for compatibility with CSV row parsing
    def __getitem__(self, item):
        # Allow accessing with original Vietnamese keys
        normalized_key = item.replace(" ", "_")
        return getattr(self, normalized_key, None)

# Serve Frontend static index page
@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h3>Error: static/index.html not found!</h3>"

# Handle submission request
@app.post("/api/submit")
async def submit_to_google_form(data: dict):
    payload = {}
    
    # Map the received keys to entry.XXXX IDs
    for key, entry_id in FIELD_MAPPING.items():
        val = data.get(key, "")
        payload[entry_id] = str(val).strip() if val is not None else ""
        
    # Ensure agreement is checkmarked
    if not payload.get("entry.1651751105"):
        payload["entry.1651751105"] = "Tôi đã đọc và đồng ý"
        
    guest_name = data.get("Họ và tên khách", "Khách")
    print(f"Submitting for guest: {guest_name}")
    
    try:
        # Submit payload via HTTP POST to Google Forms
        response = requests.post(FORM_POST_URL, data=payload, timeout=10)
        
        if response.status_code == 200:
            # Check for typical submission success indicator
            if "đã được ghi lại" in response.text or "has been recorded" in response.text or "RIVERGATE" in response.text:
                return {"success": True, "message": f"Đã gửi thông tin cho {guest_name} thành công!"}
            else:
                return {"success": False, "error": "Google Form trả về trang không xác định."}
        else:
            return {"success": False, "error": f"Lỗi phản hồi từ Google Forms: Code {response.status_code}"}
            
    except requests.exceptions.RequestException as e:
        print(f"Network error while sending request to Google Form: {e}")
        return {"success": False, "error": f"Lỗi mạng khi kết nối Google Forms: {str(e)}"}

# Parse bulk Excel/CSV file upload
@app.post("/api/upload")
async def upload_guest_list(file: UploadFile = File(...)):
    filename = file.filename
    content = await file.read()
    
    guests = []
    
    try:
        if filename.endswith(".xlsx"):
            # Parse Excel using Pandas
            df = pd.read_excel(io.BytesIO(content))
            df = df.fillna("")
            # Strip key names and convert to dictionary records
            records = df.to_dict('records')
            for rec in records:
                cleaned_rec = {str(k).strip(): str(v).strip() for k, v in rec.items()}
                guests.append(cleaned_rec)
                
        elif filename.endswith(".csv"):
            # Parse CSV
            # Try to decode content (with BOM check)
            try:
                decoded_content = content.decode('utf-8-sig')
            except UnicodeDecodeError:
                decoded_content = content.decode('latin-1')
                
            csv_reader = csv.DictReader(io.StringIO(decoded_content))
            for row in csv_reader:
                cleaned_row = {str(k).strip(): str(v).strip() for k, v in row.items() if k}
                guests.append(cleaned_row)
        else:
            return {"success": False, "error": "Định dạng tệp không được hỗ trợ. Vui lòng tải lên tệp .xlsx hoặc .csv"}
            
        print(f"Parsed {len(guests)} guests from uploaded file: {filename}")
        return {"success": True, "guests": guests}
        
    except Exception as e:
        print(f"Error parsing file {filename}: {e}")
        return {"success": False, "error": f"Không thể đọc cấu trúc tệp dữ liệu: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    # Render binds the port using the PORT env variable
    port = int(os.environ.get("PORT", 8080))
    print(f"Khởi chạy Server tại cổng {port}...")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
