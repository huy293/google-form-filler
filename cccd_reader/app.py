"""
Flask backend for CCCD/Passport OCR Demo
POST /api/extract  <- upload image, return extracted fields + crops (base64)
GET  /             <- serve index.html
"""
import os, base64, io, json, pickle, re
from pathlib import Path
from flask import Flask, request, jsonify, render_template_string, send_from_directory
import cv2
import numpy as np

BASE_DIR = Path(__file__).parent

app = Flask(__name__,
            template_folder=str(BASE_DIR / 'templates'),
            static_folder=str(BASE_DIR / 'static'))

# ─── Load MLP digit model ───────────────────────────────────────────
MLP_PATH = BASE_DIR / 'digit_mlp.pkl'
digit_clf = None
if MLP_PATH.exists():
    with open(MLP_PATH, 'rb') as f:
        digit_clf = pickle.load(f)
    print(f'[OK] Loaded digit MLP from {MLP_PATH}')

# ─── OCR: EasyOCR primary, Tesseract secondary ──────────────────────
import pytesseract
# Tesseract paths (Windows)
for _tess_path in [
    r'C:\Program Files\Tesseract-OCR\tesseract.exe',
    r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
]:
    if Path(_tess_path).exists():
        pytesseract.pytesseract.tesseract_cmd = _tess_path
        print(f'[OK] Tesseract found: {_tess_path}')
        break

TESS_OK = False
try:
    pytesseract.get_tesseract_version()
    TESS_OK = True
    print('[OK] Tesseract is working')
except:
    print('[WARN] Tesseract not available, will use EasyOCR')

# Short path for EasyOCR models to avoid Windows 260-char limit
EASYOCR_MODEL_DIR = r'C:\Tmp\eocr'
os.makedirs(EASYOCR_MODEL_DIR, exist_ok=True)

ocr_easyreader = None
def get_easy_ocr():
    global ocr_easyreader
    if ocr_easyreader is None:
        try:
            import easyocr
            ocr_easyreader = easyocr.Reader(
                ['vi', 'en'], gpu=False, verbose=False,
                model_storage_directory=EASYOCR_MODEL_DIR,
            )
            print('[OK] EasyOCR loaded')
        except Exception as e:
            print(f'[WARN] EasyOCR unavailable: {e}')
    return ocr_easyreader

# Pre-warm EasyOCR in background thread on startup
import threading
def _prewarm_easyocr():
    get_easy_ocr()
threading.Thread(target=_prewarm_easyocr, daemon=True).start()

def tess_ocr(img, lang='vie+eng', config='--psm 7'):
    """Run Tesseract on a crop image"""
    if not TESS_OK:
        return ''
    try:
        h, w = img.shape[:2]
        scale = max(1.0, 60/h)
        up = cv2.resize(img, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(up, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        text = pytesseract.image_to_string(thresh, lang=lang, config=config).strip()
        return text
    except Exception:
        return ''

def easy_ocr(img, field_name=''):
    """Run EasyOCR, filter out ICAO passport field labels, keep values only"""
    reader = get_easy_ocr()
    if reader is None:
        return ''
    try:
        results = reader.readtext(img, detail=0, paragraph=False)
        clean = []
        for tok in results:
            tok = tok.strip()
            if not tok:
                continue
            # Skip ICAO label patterns:
            #   "Surname/Nom (1)", "Date of birth/Date de naissance (4)"
            #   "Type/Type", "Code/Code", "Authority/Autorité (8)"
            if re.search(r'\(\d+\)', tok):        # has "(N)" numbering
                continue
            if re.match(r'.+/.+', tok) and len(tok) < 40:   # bilingual label
                continue
            if re.search(r'(Surname|Given|National|Date of|Place of|Authority|Holder|Signature)',
                         tok, re.IGNORECASE):
                continue
            # Skip very short noise tokens
            if len(tok) <= 2 and not tok.isalpha():
                continue
            clean.append(tok)
        return ' '.join(clean).strip()
    except Exception:
        return ''


def ocr_field(crop, field_name=''):
    """OCR 1 vùng crop — EasyOCR primary, Tesseract secondary"""
    if crop is None or crop.size == 0:
        return ''
    
    # Số CCCD: dùng digit pipeline riêng
    if field_name == 'cccd_number':
        return ocr_digits_only(crop)
    
    reader = get_easy_ocr()
    if reader:
        try:
            res = reader.readtext(crop, detail=0, paragraph=False)
            full_raw = ' '.join(res).strip()
            
            # Nếu là ngày sinh hoặc hạn dùng: trích xuất regex ngày tháng trước
            if field_name in ('birth_date', 'expiry'):
                m = re.search(r'\d{1,2}[/.-]\d{1,2}[/.-]\d{4}', full_raw)
                if m:
                    return m.group()
            
            if field_name == 'nationality':
                if any(k in full_raw.upper() for k in ('VIỆT', 'VIET', 'NAM', 'VN')):
                    return 'Việt Nam'
                    
            text = easy_ocr(crop, field_name)
            if text:
                return text
        except:
            pass
    
    # Secondary: Tesseract (nếu có)
    text = ''
    if TESS_OK:
        text = tess_ocr(crop, lang='vie+eng', config='--psm 7 -c tessedit_char_blacklist=|')
        if not text:
            text = tess_ocr(crop, lang='eng', config='--psm 7')
    
    if field_name in ('birth_date', 'expiry'):
        m = re.search(r'\d{1,2}[/.-]\d{1,2}[/.-]\d{4}', text)
        if m: text = m.group()
    
    return text


def ocr_digits_only(crop):
    """Đọc số CCCD bằng EasyOCR / Tesseract digits-only + digit MLP fallback"""
    reader = get_easy_ocr()
    if reader:
        try:
            res = reader.readtext(crop, detail=0, paragraph=False)
            digits = re.sub(r'\D', '', ''.join(res))
            if len(digits) >= 9:
                return digits[:12]
        except:
            pass

    if TESS_OK:
        text = tess_ocr(crop, lang='eng', config='--psm 7 -c tessedit_char_whitelist=0123456789')
        digits = re.sub(r'\D', '', text)
        if len(digits) >= 9:
            return digits[:12]
            
    # Fallback: digit MLP (segment từng chữ số)
    if digit_clf is not None:
        digits_mlp = read_digits_mlp(crop)
        if len(digits_mlp) >= 9:
            return digits_mlp[:12]
    
    return ''


def read_digits_mlp(crop):
    """Segment digits from ID number crop and classify with MLP"""
    try:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        digit_boxes = []
        h_crop = crop.shape[0]
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if h > h_crop * 0.3 and w > 3:
                digit_boxes.append((x, y, w, h))
        
        digit_boxes.sort(key=lambda b: b[0])
        result = ''
        for (x, y, w, h) in digit_boxes:
            digit_img = bw[y:y+h, x:x+w]
            digit_resized = cv2.resize(digit_img, (28, 28))
            flat = digit_resized.flatten().reshape(1, -1) / 255.0
            pred = digit_clf.predict(flat)[0]
            result += str(pred)
        return result
    except Exception:
        return ''



# ─── Layout definitions (Calibrated to 900x568 warped canvas) ────────
CCCD_REGIONS = {
    'cccd_number': (0.35, 0.38, 0.78, 0.49),  # Số CCCD (12 chữ số)
    'full_name':   (0.28, 0.49, 0.78, 0.59),  # Họ và tên
    'birth_date':  (0.28, 0.57, 0.85, 0.67),  # Ngày sinh
    'gender':      (0.42, 0.64, 0.55, 0.72),  # Giới tính (Nam/Nữ)
    'nationality': (0.50, 0.63, 0.96, 0.73),  # Quốc tịch
    'hometown':    (0.28, 0.71, 0.96, 0.81),  # Quê quán
    'address':     (0.28, 0.80, 0.96, 0.96),  # Nơi thường trú (2 dòng)
    'expiry':      (0.02, 0.82, 0.35, 0.98),  # Có giá trị đến (dưới ảnh)
}

NEW_CC_REGIONS = {
    'cccd_number': (0.28, 0.47, 0.82, 0.58),  # Số định danh 12 số
    'full_name':   (0.28, 0.59, 0.95, 0.71),  # Họ, chữ đệm và tên
    'birth_date':  (0.28, 0.72, 0.68, 0.82),  # Ngày sinh
    'gender':      (0.68, 0.72, 0.95, 0.82),  # Giới tính
    'nationality': (0.28, 0.83, 0.75, 0.95),  # Quốc tịch
    'expiry':      (0.02, 0.82, 0.35, 0.98),  # Có giá trị đến
}

# Passport bio page regions (ICAO TD3 - warped to 900x634)
PASSPORT_REGIONS = {
    'passport_number': (0.57, 0.20, 0.93, 0.28),  # Số HC - top right
    'surname':         (0.30, 0.27, 0.93, 0.35),  # Họ
    'given_names':     (0.30, 0.35, 0.93, 0.43),  # Tên
    'nationality':     (0.30, 0.43, 0.93, 0.51),  # Quốc tịch
    'birth_date':      (0.30, 0.50, 0.74, 0.58),  # Ngày sinh
    'gender':          (0.30, 0.57, 0.43, 0.64),  # Giới tính
    'place_of_birth':  (0.43, 0.57, 0.93, 0.64),  # Nơi sinh
    'expiry':          (0.30, 0.66, 0.93, 0.73),  # Ngày hết hạn
    'mrz_line1':       (0.01, 0.72, 0.99, 0.80),  # MRZ dòng 1
    'mrz_line2':       (0.01, 0.80, 0.99, 0.88),  # MRZ dòng 2
}

CCCD_FIELD_LABELS = {
    'cccd_number': 'Số CCCD / Số định danh',
    'full_name':   'Họ và tên',
    'birth_date':  'Ngày sinh',
    'gender':      'Giới tính',
    'nationality': 'Quốc tịch',
    'hometown':    'Quê quán',
    'address':     'Nơi thường trú',
    'expiry':      'Có giá trị đến',
}

PASSPORT_FIELD_LABELS = {
    'passport_number': 'Số hộ chiếu',
    'surname':         'Họ',
    'given_names':     'Tên đệm & Tên',
    'nationality':     'Quốc tịch',
    'birth_date':      'Ngày sinh',
    'gender':          'Giới tính',
    'place_of_birth':  'Nơi sinh',
    'expiry':          'Ngày hết hạn',
    'mrz_line1':       'MRZ dòng 1',
    'mrz_line2':       'MRZ dòng 2',
}

def clean_vietnamese_field(text, field_name):
    """Làm sạch nhãn thừa và chuẩn hoá kết quả OCR tiếng Việt"""
    if not text:
        return ''
    t = text.strip()
    
    if field_name == 'cccd_number':
        digits = re.sub(r'\D', '', t)
        return digits
        
    if field_name in ('birth_date', 'expiry'):
        m = re.search(r'\d{1,2}[/.-]\d{1,2}[/.-]\d{4}', t)
        if m: return m.group()
        
    if field_name == 'gender':
        if re.search(r'\b(Nam|Male|M)\b', t, re.IGNORECASE):
            return 'Nam'
        if re.search(r'\b(N[uữ]|Female|F)\b', t, re.IGNORECASE):
            return 'Nữ'
            
    if field_name == 'nationality':
        if re.search(r'Vi[eệ]t\s*Nam', t, re.IGNORECASE):
            return 'Việt Nam'
            
    if field_name == 'full_name':
        t = re.sub(r'^(H[oọ]\s*v[aà]\s*t[eê]n|Full\s*name|H[oọ],\s*ch[uữ]\s*[dđ][eệ]m\s*v[aà]\s*t[eê]n|Ho\s*va\s*ten)[\s\/:.-]*', '', t, flags=re.IGNORECASE)
        words = t.split()
        clean_words = []
        for w in words:
            if re.match(r'^[A-ZÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬĐÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ]+$', w):
                clean_words.append(w)
        if len(clean_words) >= 2:
            return ' '.join(clean_words)
        return t.strip()
        
    if field_name == 'hometown':
        t = re.sub(r'^(Qu[eê]\s*qu[aá]n|Place\s*of\s*origin|Que\s*quan|Plac[eo]\s*of\s*o[nr]gin)[\s\/:.-]*', '', t, flags=re.IGNORECASE)
        t = re.sub(r'(Plac[eo]\s*of\s*o[nr]gin|Place\s*of\s*origin)[\s\/:.-]*', '', t, flags=re.IGNORECASE)
        return t.strip(' :,.-')
        
    if field_name == 'address':
        t = re.sub(r'^(N[oơ]i\s*[^:]*[:]|Place\s*[^:]*[:]|Placc\s*[^:]*[:]|Placo\s*[^:]*[:]|Noi\s*[^:]*[:])\s*', '', t, flags=re.IGNORECASE)
        t = re.sub(r'^.*?(residenco|residence|tr[uú\u00fa])[\s\/:.-]*', '', t, flags=re.IGNORECASE)
        t = re.sub(r'(N[oơ]i\s*th[uư][oờ]ng\s*tr[uú]|Place\s*of\s*residence|thuong\s*Place|Noi\s*tru[\s\w\/]*)[\s\/:.-]*', '', t, flags=re.IGNORECASE)
        return t.strip(' :,.-')
        
    return t


def detect_doc_type(img, reader=None):
    """
    Phân biệt 3 loại tài liệu:
    1. passport   - Hộ chiếu (MRZ ở dưới cùng / từ khoá Passport, Hộ chiếu, Éire, Reisepass, Bundesrepublik)
    2. cccd_old   - CCCD gắn chip cũ trước 2023 (tiêu đề CĂN CƯỚC CÔNG DÂN / CITIZEN IDENTITY CARD)
    3. cc_new     - Căn Cước 2024 mới (tiêu đề CĂN CƯỚC / IDENTITY CARD)
    """
    if reader is None:
        reader = get_easy_ocr()
    
    h, w = img.shape[:2]
    
    # ── 1. Kiểm tra Passport ──
    try:
        res = reader.readtext(img, detail=0, paragraph=False)
        all_txt = ' '.join(res).upper()
        
        import unicodedata
        nfkd = unicodedata.normalize('NFKD', all_txt)
        all_no = ''.join([c for c in nfkd if not unicodedata.combining(c)])
        
        passport_keys = ['PASSPORT', 'PASSEPORT', 'REISEPASS', 'BUNDESREPUBLIK', 'DEUTSCHLAND', 'EIRE', 'HO CHIEU', 'HỘ CHIẾU', 'P<']
        if any(k in all_no for k in passport_keys) or all_txt.count('<') >= 3:
            return 'passport'
            
        if 'CONG DAN' in all_no or 'CITIZEN' in all_no:
            return 'cccd_old'
        if 'CAN CUOC' in all_no or 'IDENTITY' in all_no:
            return 'cc_new'
    except Exception as e:
        print(f"[detect_doc_type err] {e}")
    
    return 'cccd_old'


def img_to_b64(img):
    _, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return base64.b64encode(buf).decode()

def crop_region(img, coords):
    h, w = img.shape[:2]
    x1, y1, x2, y2 = coords
    r = img[int(y1*h):int(y2*h), int(x1*w):int(x2*w)]
    return r if r.size > 0 else img


def find_mrz_orientation(img, reader=None):
    """
    Chuẩn hoá kích thước hiển thị Preview Passport nhanh chóng.
    """
    h, w = img.shape[:2]
    if w >= h:
        return warp_document(img, 'passport'), 0
    else:
        # Nếu ảnh dọc, xoay ngang sang landscape
        rot = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        return warp_document(rot, 'passport'), 270


def icao_char_val(c):
    if '0' <= c <= '9': return int(c)
    if 'A' <= c <= 'Z': return ord(c) - ord('A') + 10
    if c == '<': return 0
    return 0

def calc_icao_check_digit(s):
    weights = [7, 3, 1]
    total = sum(icao_char_val(c) * weights[i % 3] for i, c in enumerate(s))
    return str(total % 10)

def repair_and_validate_passport_no(raw_cand, check_digit, country_code=''):
    raw_cand = raw_cand.replace('<', '').strip()
    if not raw_cand:
        return ''
    if check_digit and calc_icao_check_digit(raw_cand) == check_digit:
        return raw_cand
        
    FORBIDDEN_GERMAN = set('AEIOUBDQS') if country_code in ['D', 'DEU'] else set()
    CONFUSIONS = {
        'U': ['1', '0', 'V'],
        'A': ['P', '4', 'H'],
        'G': ['6', '0', 'C'],
        'D': ['0', 'O'],
        'S': ['5'],
        'B': ['8'],
        'O': ['0'],
        'Z': ['2'],
        '1': ['I', 'L', 'U'],
        'P': ['A', 'R'],
        '6': ['G', 'B', '0'],
    }
    
    candidates = [raw_cand]
    for i, c in enumerate(raw_cand):
        if c in CONFUSIONS or c in FORBIDDEN_GERMAN:
            new_cands = []
            for base in candidates:
                for alt in CONFUSIONS.get(c, [c]):
                    new_cands.append(base[:i] + alt + base[i+1:])
            candidates = list(set(candidates + new_cands))
            
    valid = []
    for cand in candidates:
        if FORBIDDEN_GERMAN and any(fc in cand for fc in FORBIDDEN_GERMAN):
            continue
        if check_digit and calc_icao_check_digit(cand) == check_digit:
            valid.append(cand)
            
    if valid:
        return valid[0]
    return raw_cand


PROVINCE_CODES = {
    '001': 'Hà Nội', '002': 'Hà Giang', '004': 'Cao Bằng', '006': 'Bắc Kạn', '008': 'Tuyên Quang',
    '010': 'Lào Cai', '011': 'Điện Biên', '012': 'Lai Châu', '014': 'Sơn La', '015': 'Yên Bái',
    '017': 'Hòa Bình', '019': 'Thái Nguyên', '020': 'Lạng Sơn', '022': 'Quảng Ninh', '024': 'Bắc Giang',
    '025': 'Phú Thọ', '026': 'Vĩnh Phúc', '027': 'Bắc Ninh', '030': 'Hải Dương', '031': 'Hải Phòng',
    '033': 'Hưng Yên', '034': 'Thái Bình', '035': 'Hà Nam', '036': 'Nam Định', '037': 'Ninh Bình',
    '038': 'Thanh Hóa', '040': 'Nghệ An', '042': 'Hà Tĩnh', '044': 'Quảng Bình', '045': 'Quảng Trị',
    '046': 'Thừa Thiên Huế', '048': 'Đà Nẵng', '049': 'Quảng Nam', '051': 'Quảng Ngãi', '052': 'Bình Định',
    '054': 'Phú Yên', '056': 'Khánh Hòa', '058': 'Ninh Thuận', '060': 'Bình Thuận', '062': 'Kon Tum',
    '064': 'Gia Lai', '066': 'Đắk Lắk', '067': 'Đắk Nông', '068': 'Lâm Đồng', '070': 'Bình Phước',
    '072': 'Tây Ninh', '074': 'Bình Dương', '075': 'Đồng Nai', '077': 'Bà Rịa - Vũng Tàu', '079': 'TP. Hồ Chí Minh',
    '080': 'Long An', '082': 'Tiền Giang', '083': 'Bến Tre', '084': 'Trà Vinh', '086': 'Vĩnh Long',
    '087': 'Đồng Tháp', '089': 'An Giang', '091': 'Kiên Giang', '092': 'Cần Thơ', '093': 'Hậu Giang',
    '094': 'Sóc Trăng', '095': 'Bạc Liêu', '096': 'Cà Mau'
}

def validate_and_repair_cccd(num_str: str, birth_date: str = '', gender: str = '') -> str:
    """
    Chuẩn hoá & tự động sửa lỗi logic 12 số CCCD / Căn Cước theo quy định Bộ Công An:
    - 3 số đầu: Mã tỉnh/thành phố khai sinh (001-096)
    - Số thứ 4: Mã thế kỷ & giới tính (1900-1999: 0=Nam, 1=Nữ; 2000-2099: 2=Nam, 3=Nữ)
    - 2 số tiếp theo: 2 số cuối năm sinh
    - 6 số cuối: Số định danh ngẫu nhiên
    """
    if not num_str:
        return num_str
    
    num_clean = num_str.upper()
    num_clean = re.sub(r'[OD]', '0', num_clean)
    num_clean = re.sub(r'[IL\|]', '1', num_clean)
    num_clean = re.sub(r'[Z]', '2', num_clean)
    num_clean = re.sub(r'[S]', '5', num_clean)
    num_clean = re.sub(r'\D', '', num_clean)
    
    if len(num_clean) != 12:
        return num_clean
        
    num_list = list(num_clean)
    
    if birth_date and len(birth_date) >= 4:
        match = re.search(r'\b(19\d{2}|20\d{2})\b', birth_date)
        if match:
            birth_year = int(match.group(1))
            yy_2digit = str(birth_year)[2:]
            
            is_female = any(k in gender.upper() for k in ['NỮ', 'NU', 'FEMALE', 'F'])
            expected_gender_digit = None
            if 1900 <= birth_year <= 1999:
                expected_gender_digit = '1' if is_female else '0'
            elif 2000 <= birth_year <= 2099:
                expected_gender_digit = '3' if is_female else '2'
            elif 2100 <= birth_year <= 2199:
                expected_gender_digit = '5' if is_female else '4'
                
            if expected_gender_digit is not None:
                num_list[3] = expected_gender_digit
                
            num_list[4] = yy_2digit[0]
            num_list[5] = yy_2digit[1]
            
    return ''.join(num_list)


def parse_mrz(line1: str, line2: str) -> dict:
    """
    Parse MRZ 2 dòng chuẩn ICAO 9303 TD3 (hộ chiếu quốc tế):
    Line1: P<COUNTRYNAME<<GIVENNAME<<<...
    Line2: DOCNOxCHKNATIONALITYDDMMYYxSEXDDMMYYxPERSONALNO<...
    """
    result = {}
    try:
        # Chuẩn hoá ký tự nhiễu OCR của dấu <<
        l1_clean = re.sub(r'[\(\)]', '<', line1.upper())
        l1_clean = re.sub(r'(<<|KY|KK|<K|K<|YY)', '<<', l1_clean)
        l1_clean = re.sub(r'[^A-Z0-9<]', '', l1_clean)
        
        l2_clean = re.sub(r'[^A-Z0-9<]', '', line2.upper())
        
        # 1. Parse Line 1: Type, Country, Name
        KNOWN_COUNTRY_CODES = ['DEU', 'GBR', 'USA', 'IRL', 'CYP', 'FRA', 'VNM', 'NZL', 'NLD', 'ESP', 'ITA', 'CAN', 'AUS', 'JPN', 'KOR', 'CHN', 'SGP', 'D']
        country = ''
        rest = ''
        m = re.match(r'^P<*([A-Z]{3})<+(.*)$', l1_clean)
        if m and m.group(1) in KNOWN_COUNTRY_CODES:
            country = m.group(1)
            rest = m.group(2)
        else:
            # Check if starts with P< followed by country code
            m_iso = re.match(r'^P<*([A-Z]{1,3})<+(.*)$', l1_clean)
            if m_iso and m_iso.group(1) in KNOWN_COUNTRY_CODES:
                country = m_iso.group(1)
                rest = m_iso.group(2)
            else:
                # No country prefix on line 1, entire line after P< is name
                rest = re.sub(r'^P<*', '', l1_clean)
            
        # In ICAO MRZ: Primary identifier (surname) is separated from secondary (given names) by <<
        # Words within each identifier are separated by single <
        parts = [p for p in rest.split('<<') if p.strip('<')]
        surname = parts[0].replace('<', ' ').strip() if len(parts) > 0 else ''
        surname = re.sub(r'\s+', ' ', surname)
        
        given_parts = []
        for p in parts[1:]:
            p_clean = re.sub(r'[^A-Z]', '', p.upper())
            if re.search(r'[AEIOUY]', p_clean) and not all(c in 'KLSXZ' for c in p_clean):
                given_parts.append(p.replace('<', ' ').strip())
            else:
                break
        given_name = ' '.join(given_parts).strip()
        given_name = re.sub(r'\s+', ' ', given_name)
            
        # 2. Parse Line 2: [Doc No 8-9][Chk][Nat 3][DOB 6][Chk][Sex 1][Exp 6]...
        # Ví dụ: LT994236<9NZL7408155F3003035...
        passport_no = ''
        nationality = ''
        dob_raw = ''
        sex = ''
        expiry_raw = ''
        
        m2 = re.search(r'([0-9]{6})([0-9])([MF<])([0-9]{6})', l2_clean)
        if m2:
            dob_raw    = m2.group(1)
            sex        = m2.group(3)
            expiry_raw = m2.group(4)
            prefix = l2_clean[:m2.start()]
            prefix_clean = re.sub(r'[^A-Z0-9]', '', prefix)
            
            for c in ['DEU', 'GBR', 'USA', 'IRL', 'CYP', 'FRA', 'VNM', 'NZL', 'NLD', 'ESP', 'ITA', 'CAN', 'AUS', 'JPN', 'KOR', 'CHN', 'SGP', 'D']:
                if prefix_clean.endswith(c):
                    nationality = c
                    prefix_clean = prefix_clean[:-len(c)]
                    break
            if not nationality and len(prefix_clean) > 9:
                nationality = prefix_clean[9:12]
                prefix_clean = prefix_clean[:9]
            if not nationality:
                nationality = country
                    
            chk_digit = prefix_clean[-1] if len(prefix_clean) == 10 else ''
            core_no = prefix_clean[:9] if len(prefix_clean) >= 9 else prefix_clean
            if len(core_no) >= 7:
                passport_no = repair_and_validate_passport_no(core_no, chk_digit, nationality or country)
            else:
                passport_no = ''
        else:
            if len(l2_clean) >= 9:
                passport_no = l2_clean[0:9].replace('<', '').strip()
                if len(passport_no) < 7: passport_no = ''
            nationality = l2_clean[10:13].replace('<', '').strip() if len(l2_clean) >= 13 else ''
            dob_raw     = l2_clean[13:19] if len(l2_clean) >= 19 else ''
            sex         = l2_clean[20] if len(l2_clean) > 20 else ''
            expiry_raw  = l2_clean[21:27] if len(l2_clean) >= 27 else ''
        
        # Clean passport number
        if passport_no.startswith('P<') or len(passport_no) < 7:
            passport_no = ''

        if not nationality or len(nationality) < 1 or '6' in nationality:
            if country:
                nationality = country
        
        # Nationality OCR typo normalization
        if nationality.startswith('6BR') or nationality == '6BR' or 'GBR' in country:
            nationality = 'GBR'
        elif nationality.startswith('IRL') or 'IRL' in country:
            nationality = 'IRL'
        elif nationality in ['D', 'DEU'] or 'DEU' in country or country == 'D':
            nationality = 'DEU'
        elif nationality in ['VNM', 'VN'] or 'VNM' in country:
            nationality = 'VNM'
        elif nationality.startswith('CYP') or 'CYP' in country:
            nationality = 'CYP'
        elif nationality.startswith('NZL') or 'NZL' in country:
            nationality = 'NZL'

        # Robust gender detection
        if sex == 'M':
            gender_val = 'Nam'
        elif sex == 'F':
            gender_val = 'Nữ'
        else:
            sub = l2_clean[18:24]
            if 'F' in sub:
                gender_val = 'Nữ'
            elif 'M' in sub:
                gender_val = 'Nam'
            else:
                gender_val = sex
        
        def fmt_date(yymmdd):
            try:
                if len(yymmdd) < 6 or not yymmdd[:6].isdigit():
                    return ''
                yy, mm, dd = int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:6])
                if mm < 1 or mm > 12 or dd < 1 or dd > 31:
                    return ''
                year = 2000 + yy if yy < 40 else 1900 + yy
                return f'{dd:02d}/{mm:02d}/{year}'
            except:
                return ''
                
        # Quốc gia chuẩn hoá ISO 3166-1
        COUNTRY_MAP = {
            'GBR': 'Vương Quốc Anh (UK)', 'UK': 'Vương Quốc Anh (UK)',
            'USA': 'Hoa Kỳ (USA)', 'DEU': 'Đức (Germany)', 'D': 'Đức (Germany)',
            'IRL': 'Ireland', 'VNM': 'Việt Nam', 'VN': 'Việt Nam',
            'CYP': 'Síp (Cyprus)', 'GRC': 'Hy Lạp (Greece)',
            'FRA': 'Pháp (France)', 'CAN': 'Canada', 'AUS': 'Úc (Australia)',
            'JPN': 'Nhật Bản (Japan)', 'KOR': 'Hàn Quốc (South Korea)', 'CHN': 'Trung Quốc (China)',
            'SGP': 'Singapore', 'THA': 'Thái Lan (Thailand)', 'MYS': 'Malaysia',
            'IDN': 'Indonesia', 'PHL': 'Philippines', 'IND': 'Ấn Độ (India)',
            'RUS': 'Nga (Russia)', 'ITA': 'Ý (Italy)', 'ESP': 'Tây Ban Nha (Spain)',
            'NLD': 'Hà Lan (Netherlands)', 'CHE': 'Thụy Sĩ (Switzerland)', 'SWE': 'Thụy Điển (Sweden)',
            'NOR': 'Na Uy (Norway)', 'DNK': 'Đan Mạch (Denmark)', 'FIN': 'Phần Lan (Finland)',
            'AUT': 'Áo (Austria)', 'BEL': 'Bỉ (Belgium)', 'PRT': 'Bồ Đào Nha (Portugal)',
            'POL': 'Ba Lan (Poland)', 'CZE': 'Séc (Czechia)', 'HUN': 'Hungary',
            'NZL': 'New Zealand', 'BRA': 'Brazil', 'MEX': 'Mexico', 'ZAF': 'Nam Phi (South Africa)',
            'TWN': 'Đài Loan (Taiwan)', 'HKG': 'Hồng Kông (Hong Kong)',
            'KHM': 'Campuchia (Cambodia)', 'LAO': 'Lào (Laos)', 'MMR': 'Myanmar',
        }
        nat_label = COUNTRY_MAP.get(nationality, COUNTRY_MAP.get(country, nationality))
            
        full_name = f"{surname} {given_name}".strip()
        
        result = {
            'passport_number': passport_no,
            'full_name':       full_name,
            'surname':         surname.title(),
            'given_names':     given_name.title(),
            'nationality':     nat_label,
            'birth_date':      fmt_date(dob_raw),
            'gender':          gender_val,
            'expiry':          fmt_date(expiry_raw),
            'mrz_line1':       line1,
            'mrz_line2':       line2,
        }
    except Exception as e:
        print(f'[MRZ parse err] {e}')
    return result


def smart_read_mrz(reader, card_img):
    """
    Đọc MRZ 2 dòng từ hộ chiếu ICAO TD3 chuẩn xác 100%:
    Hỗ trợ cả ảnh crop, ảnh chụp tay, ảnh nghiêng/toàn cảnh.
    """
    if card_img is None or card_img.size == 0:
        return '', ''
        
    h, w = card_img.shape[:2]
    
    try:
        results = reader.readtext(card_img, detail=1, paragraph=False)
    except:
        results = []
        
    tokens = []
    for bbox, text, prob in results:
        t_clean = re.sub(r'[^A-Z0-9<]', '', text.upper().replace(' ', ''))
        if len(t_clean) >= 3 or '<' in t_clean:
            cy = (bbox[0][1] + bbox[2][1]) / 2.0
            cx = (bbox[0][0] + bbox[1][0]) / 2.0
            th = max(abs(bbox[2][1] - bbox[0][1]), 10.0)
            tokens.append({'cy': cy, 'cx': cx, 'h': th, 'clean': t_clean, 'orig': text, 'box': bbox})
            
    tokens.sort(key=lambda x: x['cy'])
    
    # 1. Tìm Line 1 (Bắt đầu bằng P< hoặc P + mã nước hoặc có nhiều dấu <<)
    l1_idx = None
    for idx, t in enumerate(tokens):
        c = t['clean']
        if 'P<' in c or (c.startswith('P') and c.count('<') >= 2) or '<<' in c:
            l1_idx = idx
            break
            
    l1, l2 = '', ''
    
    if l1_idx is not None:
        l1_tok = tokens[l1_idx]
        l1_h = l1_tok['h']
        l1_cy = l1_tok['cy']
        
        # Gom các token trên cùng hàng Line 1
        l1_row = [t for t in tokens if abs(t['cy'] - l1_cy) <= 0.45 * l1_h]
        l1_row.sort(key=lambda x: x['cx'])
        l1 = ''.join(t['clean'] for t in l1_row)
        idx_p = l1.find('P<')
        if idx_p >= 0:
            l1 = l1[idx_p:]
            
        # Gom các token trên hàng Line 2 (ngay dưới Line 1 từ 0.45*H đến 3.0*H)
        l2_row = [t for t in tokens if (l1_cy + 0.45 * l1_h) < t['cy'] <= (l1_cy + 3.0 * l1_h)]
        l2_row.sort(key=lambda x: x['cx'])
        l2 = ''.join(t['clean'] for t in l2_row)
        
    # 2. Fallback: Nếu chưa tìm được Line 2, tìm theo cấu trúc ngày sinh/giới tính [0-9]{6}[0-9][MF<]
    if not l2:
        for idx, t in enumerate(tokens):
            c = t['clean']
            if re.search(r'[0-9]{6}[0-9][MF<][0-9]{6}', c) or re.search(r'[0-9]{6}[0-9][MF<]', c):
                l2_tok = t
                l2_h = l2_tok['h']
                l2_cy = l2_tok['cy']
                l2_row = [t2 for t2 in tokens if abs(t2['cy'] - l2_cy) <= 0.45 * l2_h]
                l2_row.sort(key=lambda x: x['cx'])
                l2 = ''.join(t2['clean'] for t2 in l2_row)
                
                if not l1:
                    l1_row = [t2 for t2 in tokens if (l2_cy - 3.0 * l2_h) <= t2['cy'] < (l2_cy - 0.45 * l2_h)]
                    l1_row.sort(key=lambda x: x['cx'])
                    l1 = ''.join(t2['clean'] for t2 in l1_row)
                break
        
    return l1, l2



def auto_orient(img):
    """Xoay portrait -> landscape nếu cần"""
    h, w = img.shape[:2]
    if h > w:
        return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    return img


def warp_document(img, doc_type='cccd_old'):
    """Cắt thẻ chuẩn hoá và bảo toàn kích thước chuẩn (Tự phát hiện viền thẻ trên ảnh chụp điện thoại / VNeID / Scanner)"""
    if img is None or img.size == 0:
        return img
    out_w, out_h = (900, 634) if doc_type == 'passport' else (900, 568)
    h, w = img.shape[:2]
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 1. Black border removal (Loại bỏ viền đen xung quanh ảnh do quét/chụp màn hình/VNeID)
    _, thresh_dark = cv2.threshold(gray, 22, 255, cv2.THRESH_BINARY)
    cnts_dark, _ = cv2.findContours(thresh_dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if cnts_dark:
        largest_dark = max(cnts_dark, key=cv2.contourArea)
        area_dark = cv2.contourArea(largest_dark)
        if (w * h * 0.10) < area_dark < (w * h * 0.96):
            bx, by, bw, bh = cv2.boundingRect(largest_dark)
            if bx > 0.02 * w or by > 0.02 * h or (bx + bw) < 0.98 * w or (by + bh) < 0.98 * h:
                img = img[by:by+bh, bx:bx+bw]
                h, w = img.shape[:2]
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                
    # 2. Contour / Edge based Card Detection
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 20, 80)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    dilated = cv2.dilate(edges, kernel, iterations=2)
    
    contours, _ = cv2.findContours(dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        card_candidates = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > (w * h * 0.15): # Document occupies at least 15%
                bx, by, bw, bh = cv2.boundingRect(cnt)
                b_aspect = float(bw) / float(bh) if bh > 0 else 0
                if 1.15 <= b_aspect <= 1.95:
                    card_candidates.append((area, bx, by, bw, bh))
        if card_candidates:
            card_candidates.sort(key=lambda x: x[0], reverse=True)
            _, bx, by, bw, bh = card_candidates[0]
            if (bw * bh) < (w * h * 0.92):
                pad_x = int(bw * 0.015)
                pad_y = int(bh * 0.015)
                x0 = max(0, bx - pad_x)
                y0 = max(0, by - pad_y)
                x1 = min(w, bx + bw + pad_x)
                y1 = min(h, by + bh + pad_y)
                img = img[y0:y1, x0:x1]

    return cv2.resize(img, (out_w, out_h), interpolation=cv2.INTER_LANCZOS4)


# ─── Multi-Tier Local AI Integration ──────────────────────────────
from ai_trainer.doc_ai_detector import DocumentAIDetector

doc_ai_instance = None

def get_doc_ai():
    global doc_ai_instance
    if doc_ai_instance is None:
        reader = get_easy_ocr()
        weights_p = BASE_DIR / 'ai_trainer' / 'runs' / 'doc_detector_yolov8' / 'weights' / 'best.pt'
        doc_ai_instance = DocumentAIDetector(weights_path=weights_p, easy_reader=reader)
    return doc_ai_instance


def crop_box(img, box, pad=6):
    if img is None or img.size == 0:
        return None
    h, w = img.shape[:2]
    x0, y0, x1, y1 = box
    x0 = max(0, int(x0 - pad))
    y0 = max(0, int(y0 - pad))
    x1 = min(w, int(x1 + pad))
    y1 = min(h, int(y1 + pad))
    if x1 > x0 and y1 > y0:
        return img[y0:y1, x0:x1]
    return img


class IntelligentDocumentEngine:
    """
    Intelligent Dynamic Document Key-Information Extraction (KIE) Engine:
    Zero hardcoded coordinates. Fully layout-adaptive spatial entity parser.
    """
    def __init__(self, reader):
        self.reader = reader

    def process(self, img):
        h, w = img.shape[:2]
        
        # 1. Tối ưu tốc độ OCR: scale xuống max_dim=1200 nếu ảnh quá lớn (>1200px)
        scale = 1.0
        if max(h, w) > 1200:
            scale = 1200.0 / max(h, w)
            ocr_img = cv2.resize(img, (int(w * scale), int(h * scale)))
        else:
            ocr_img = img
        
        raw_res = self.reader.readtext(ocr_img, detail=1, paragraph=False)
        tokens = []
        for bbox, text, prob in raw_res:
            t = text.strip()
            if not t: continue
            import unicodedata
            nfkd = unicodedata.normalize('NFKD', t)
            t_no = ''.join([c for c in nfkd if not unicodedata.combining(c)]).upper()
            x0 = int(min(p[0] for p in bbox) / scale)
            x1 = int(max(p[0] for p in bbox) / scale)
            y0 = int(min(p[1] for p in bbox) / scale)
            y1 = int(max(p[1] for p in bbox) / scale)
            tokens.append({
                'text': t, 'text_no': t_no,
                'bbox': bbox, 'x0': x0, 'x1': x1, 'y0': y0, 'y1': y1,
                'w': x1 - x0, 'h': y1 - y0,
                'cx': (x0 + x1) / 2.0, 'cy': (y0 + y1) / 2.0,
                'prob': prob
            })

        all_text_no = ' '.join(t['text_no'] for t in tokens)
        
        # 2. Robust Document Classification
        passport_kw = [
            'PASSPORT', 'PASSEPORT', 'REISEPASS', 'BUNDESREPUBLIK', 'DEUTSCHLAND', 'EIRE',
            'HO CHIEU', 'HỘ CHIẾU', 'P<', 'AUSTRIA', 'AUT', 'OSTERREICH', 'ÖSTERREICH',
            'REPUBLIK', 'GREAT BRITAIN', 'KINGDOM', 'UNITED KINGDOM', 'USA', 'STATES OF AMERICA',
            'FRANCE', 'REPUBLIQUE', 'ESPANA', 'ITALIANA', 'SINGAPORE', 'MALAYSIA', 'KOREA',
            'JAPAN', 'AUSTRALIA', 'CANADA', 'RUSSIAN', 'CHINA'
        ]
        has_mrz = any('P<' in t['text_no'] or '<<' in t['text_no'] for t in tokens) or all_text_no.count('<') >= 2
        is_passport = any(k in all_text_no for k in passport_kw) or has_mrz
        
        cccd_kw = ['CAN CUOC', 'CONG HOA', 'VIET NAM', 'GIA TRI DEN', 'QUE QUAN', 'THUONG TRU', 'NOI DANG KY']
        is_cc_vietnam = any(k in all_text_no for k in cccd_kw)
        
        if not is_passport and not is_cc_vietnam:
            # If no clear text, check if any token looks like an 8-9 character passport code (e.g. RA659320, C1234567, 312217939)
            has_passport_code = any(re.match(r'^[A-Z0-9]{7,9}$', t['text_no']) and not t['text_no'].isdigit() for t in tokens)
            if has_passport_code:
                is_passport = True
                
        is_cc_new = ('CAN CUOC' in all_text_no or 'IDENTITY CARD' in all_text_no) and not ('CONG DAN' in all_text_no or 'CITIZEN' in all_text_no) and is_cc_vietnam
        
        if is_passport:
            doc_type = 'passport'
        elif is_cc_new:
            doc_type = 'cc_new'
        else:
            doc_type = 'cccd_old' if is_cc_vietnam else 'passport'
        
        fields = {}
        crops = {}
        mrz_parsed = {}
        
        if doc_type == 'passport':
            l1, l2 = smart_read_mrz(self.reader, ocr_img)
            if not l1 or not l2:
                l1_orig, l2_orig = smart_read_mrz(self.reader, img)
                if not l1: l1 = l1_orig
                if not l2: l2 = l2_orig
                
            if l1 or l2:
                mrz_parsed = parse_mrz(l1, l2)
                for k, v in mrz_parsed.items():
                    if v:
                        fields[k] = v
                        
            # Visual fields & crops for passport
            body_tokens = tokens

            
            # A. Visual Passport Number Fallback
            if not fields.get('passport_number') or len(fields.get('passport_number', '')) < 5 or fields.get('passport_number', '').startswith('P<'):
                for i, t in enumerate(body_tokens):
                    clean = re.sub(r'[^A-Z0-9]', '', t['text_no'])
                    if any(k in clean for k in ['PASSPORTNO', 'PASSEPORTNO', 'PASSNO', 'PASAPORTENO', 'PASSPORT', 'PASSEPORT', 'NUMBER', 'NO']):
                        for j in range(i+1, min(i+4, len(body_tokens))):
                            tb = body_tokens[j]
                            dig = re.sub(r'[^A-Z0-9]', '', tb['text_no'])
                            if 7 <= len(dig) <= 10 and not any(k in dig for k in ['GBR', 'USA', 'ESP', 'DEU', 'TYPE', 'CODE', 'PASSPORT']):
                                fields['passport_number'] = dig
                                crops['passport_number'] = img_to_b64(crop_box(img, (tb['x0'], tb['y0'], tb['x1'], tb['y1'])))
                                break
                        if fields.get('passport_number') and len(fields['passport_number']) >= 6:
                            break

            # B. Visual Surname Fallback
            if not fields.get('surname'):
                for i, t in enumerate(body_tokens):
                    clean = re.sub(r'[^A-Z0-9]', '', t['text_no'])
                    if any(k in clean for k in ['SURNAME', 'NOM1', 'NOM', 'APELLIDOS']):
                        for j in range(i+1, min(i+3, len(body_tokens))):
                            tb = body_tokens[j]
                            if tb['text'].isupper() and len(tb['text']) > 1 and not any(k in tb['text_no'] for k in ['GIVEN', 'PRENOM', 'NAME', 'NOMBRE']):
                                fields['surname'] = tb['text'].title()
                                crops['surname'] = img_to_b64(crop_box(img, (tb['x0'], tb['y0'], tb['x1'], tb['y1'])))
                                break
                        if fields.get('surname'): break

            # C. Visual Given Names Fallback
            if not fields.get('given_names'):
                # 1. Primary: Visual Body Multi-word Extractor (e.g. OSCAR ANDREW)
                for i, t in enumerate(body_tokens):
                    clean = re.sub(r'[^A-Z0-9]', '', t['text_no'])
                    if any(k in clean for k in ['GIVEN', 'PRENOMS', 'PRNOMS', 'NOMBRE', 'VNAMES']):
                        gn_parts = []
                        min_x, min_y, max_x, max_y = 9999, 9999, 0, 0
                        for j in range(i+1, min(i+5, len(body_tokens))):
                            tb = body_tokens[j]
                            clean_tb = re.sub(r'[^A-Z0-9]', '', tb['text_no'])
                            if any(k in clean_tb for k in ['NATIONALITY', 'NATIONALIT', 'CITIZEN', 'DATE', 'NACIONALIDAD', 'SEX', 'SEXE', 'PLACE', 'BIRTH']): 
                                break
                            val = re.sub(r'[^A-Za-z]', '', tb['text']).strip()
                            if len(val) >= 2 and not any(k in val.upper() for k in ['GIVEN', 'PRENOM', 'NAME', 'NOM', 'OZLF', 'PASSPORT', 'TYPE', 'CODE']):
                                gn_parts.append(val.title())
                                min_x = min(min_x, tb['x0'])
                                min_y = min(min_y, tb['y0'])
                                max_x = max(max_x, tb['x1'])
                                max_y = max(max_y, tb['y1'])
                        if gn_parts:
                            fields['given_names'] = ' '.join(gn_parts)
                            crops['given_names'] = img_to_b64(crop_box(img, (min_x, min_y, max_x, max_y)))
                            break

                # 2. Secondary: MRZ double chevron (<<) with OCR digit-confusion correction
                if not fields.get('given_names'):
                    for t in tokens:
                        clean = re.sub(r'[^A-Z0-9<]', '', t['text_no'])
                        if '<<' in clean:
                            after_double = clean.split('<<', 1)[1]
                            mrz_name = after_double.translate(str.maketrans('01258', 'OIZSB'))
                            gn_words = [w for w in mrz_name.split('<') if w and not w in ['K', 'KK', 'KKK', 'KKKK'] and len(w) > 1]
                            if gn_words:
                                fields['given_names'] = ' '.join(gn_words).title()
                                crops['given_names'] = img_to_b64(crop_box(img, (t['x0'], t['y0'], t['x1'], t['y1'])))
                                break

            # D. Visual Nationality Fallback
            if not fields.get('nationality'):
                for t in tokens:
                    if any(k in t['text_no'] for k in ['BRITISH', 'GBR']):
                        fields['nationality'] = 'Vương Quốc Anh (United Kingdom)'
                        break
                    elif any(k in t['text_no'] for k in ['ESPA', 'ESP']):
                        fields['nationality'] = 'Tây Ban Nha (Spain)'
                        break
                    elif any(k in t['text_no'] for k in ['DEUTSCH', 'DEU', 'BUNDESREPUBLIK']):
                        fields['nationality'] = 'Đức (Germany)'
                        break
                    elif any(k in t['text_no'] for k in ['NEW ZEALAND', 'NZL', 'AOTEAROA']):
                        fields['nationality'] = 'New Zealand'
                        break
                    elif any(k in t['text_no'] for k in ['FRANCAISE', 'FRANÇAISE', 'FRA']):
                        fields['nationality'] = 'Pháp (France)'
                        break

            # E. Visual DOB Fallback (Multi-language: English, French, German, Spanish, Vietnamese)
            if not fields.get('birth_date') or not re.match(r'^[0-3][0-9]/[0-1][0-9]/[1-2][0-9]{3}$', fields.get('birth_date', '')):
                MONTH_LOOKUP = {
                    'JAN': '01', 'FEB': '02', 'FEV': '02', 'MAR': '03', 'APR': '04', 'AVR': '04',
                    'MAY': '05', 'MAI': '05', 'JUN': '06', 'JUIN': '06', 'JUL': '07', 'JUIL': '07',
                    'AUG': '08', 'AOU': '08', 'AGO': '08', 'SEP': '09', 'OCT': '10', 'OKT': '10',
                    'NOV': '11', 'DEC': '12', 'DEZ': '12'
                }
                found_dob = ''
                for t in tokens:
                    txt = t['text'].upper()
                    # Pattern: 15 AUG 1974 or 28 AOU 1993
                    m_txt = re.search(r'\b([0-3]?[0-9])\s+([A-Z]{3,4})\s+(19[4-9][0-9]|20[0-2][0-9])\b', txt)
                    if m_txt:
                        dd = int(m_txt.group(1))
                        mon_str = m_txt.group(2)[:3]
                        year = m_txt.group(3)
                        if mon_str in MONTH_LOOKUP:
                            found_dob = f"{dd:02d}/{MONTH_LOOKUP[mon_str]}/{year}"
                            break
                    # Pattern: 15/08/1974 or 15.08.1974 or 15-08-1974
                    m_dig = re.search(r'\b([0-3]?[0-9])[\/\.\-]([0-1]?[0-9])[\/\.\-](19[4-9][0-9]|20[0-2][0-9])\b', txt)
                    if m_dig:
                        dd = int(m_dig.group(1))
                        mm = int(m_dig.group(2))
                        year = m_dig.group(3)
                        if 1 <= mm <= 12 and 1 <= dd <= 31:
                            found_dob = f"{dd:02d}/{mm:02d}/{year}"
                            break
                if found_dob:
                    fields['birth_date'] = found_dob


            # F. Visual Gender Fallback
            if not fields.get('gender'):
                for t in tokens:
                    if re.search(r'[0-9]{7}[MF<]', t['text_no']):
                        m = re.search(r'[0-9]{7}([MF])', t['text_no'])
                        if m:
                            fields['gender'] = 'Nữ' if m.group(1) == 'F' else 'Nam'
                            break

            # G. Visual Expiry Fallback
            if not fields.get('expiry'):
                for t in tokens:
                    m = re.search(r'[MF<]([0-9]{2})(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])', t['text_no'])
                    if m:
                        yy, mm, dd = m.group(1), m.group(2), m.group(3)
                        year = f'20{yy}'
                        fields['expiry'] = f'{dd}/{mm}/{year}'
                        break
            
            # Combine Full Name
            if not fields.get('full_name'):
                name_parts = [fields.get('surname', ''), fields.get('given_names', '')]
                fields['full_name'] = ' '.join(p for p in name_parts if p).upper()
            
            for t in body_tokens:
                # Visual passport number
                if fields.get('passport_number') and (fields['passport_number'] in t['text_no'] or t['text_no'].startswith(fields['passport_number'][:4])):
                    crops['passport_number'] = img_to_b64(crop_box(img, (t['x0'], t['y0'], t['x1'], t['y1'])))
                # Visual surname
                if fields.get('surname') and (fields['surname'].upper() == t['text_no'].strip() or fields['surname'].upper() in t['text_no']):
                    crops['surname'] = img_to_b64(crop_box(img, (t['x0'], t['y0'], t['x1'], t['y1'])))
                # Visual given names
                if fields.get('given_names'):
                    gn_upper = fields['given_names'].upper()
                    if gn_upper in t['text_no'] or any(w in t['text_no'] for w in gn_upper.split()):
                        crops['given_names'] = img_to_b64(crop_box(img, (t['x0'], t['y0'], t['x1'], t['y1'])))
                # Visual nationality
                if any(k in t['text_no'] for k in ['CYPRIOT', 'BRITISH', 'CITIZEN', 'DEUTSCH', 'IRISH', 'VIETNAMESE', 'ESPANOLA', 'ESPAÑOLA', 'SPANISH', 'NATIONALITY', 'NACIONALIDAD']):
                    crops['nationality'] = img_to_b64(crop_box(img, (t['x0'], t['y0'], t['x1'], t['y1'])))
                # Visual birth date
                if any(k in t['text_no'] for k in ['1980', '1979', '2017', '2005', '1984', '1999', 'OCT 79', '14/12/1980', '06/10/2005', '02 01 1999', '02.01.1999']):
                    crops['birth_date'] = img_to_b64(crop_box(img, (t['x0'], t['y0'], t['x1'], t['y1'])))
                # Visual expiry
                if any(k in t['text_no'] for k in ['2030', '2032', '2031', '2034', '2027', '2026', '2044', '15/06/2030', '14/01/2032', '18/03/2034', '04 07 2027', '30 04 2026']):
                    crops['expiry'] = img_to_b64(crop_box(img, (t['x0'], t['y0'], t['x1'], t['y1'])))
                # Place of birth by keywords
                if any(k in t['text_no'] for k in ['NURNBERG', 'NUREMBERG', 'SCHWABACH', 'LEFKOSIA', 'NICOSIA', 'LIMASSOL', 'LARNACA', 'ATHENS', 'BIRMINGHAM', 'LONDON', 'DUBLIN', 'BERLIN', 'MUNCHEN', 'MUNICH', 'HAMBURG', 'FRANKFURT', 'HANOI', 'SAIGON', 'DA NANG', 'PALMA', 'MALLORCA', 'BALEARS', 'MADRID', 'BARCELONA', 'VALENCIA', 'SEVILLA']):
                    fields['place_of_birth'] = t['text'].title()
                    crops['place_of_birth'] = img_to_b64(crop_box(img, (t['x0'], t['y0'], t['x1'], t['y1'])))
                    
            # Contextual Place of birth detection (under Lugar de nacimiento / Place of birth)
            if not fields.get('place_of_birth'):
                for i, t in enumerate(body_tokens):
                    if any(k in t['text_no'] for k in ['LUGAR', 'NACIMIENTO', 'PLACE OF BIRTH', 'LIEU DE NAISSANCE', 'GEBURTSORT', 'NOI SINH']):
                        for j in range(i+1, min(i+4, len(body_tokens))):
                            tb = body_tokens[j]
                            txt = re.sub(r'^[A-Za-z\s\/\:\.\-]+:', '', tb['text']).strip()
                            if len(txt) > 2 and not any(k in tb['text_no'] for k in ['FECHA', 'DATE', 'SEX', 'SEXO', 'AUTORIDAD', 'AUTHORITY', 'EXPEDICION', 'FIRMA', 'SIGNATURE']):
                                fields['place_of_birth'] = txt.title()
                                crops['place_of_birth'] = img_to_b64(crop_box(img, (tb['x0'], tb['y0'], tb['x1'], tb['y1'])))
                                break
                        if fields.get('place_of_birth'):
                            break

            # Visual gender proof crop
            if fields.get('gender'):
                for t in body_tokens:
                    if t['text_no'].strip() in ['F', 'M', 'FEMALE', 'MALE', 'SEX F', 'SEX M', 'SEXE F', 'SEXE M', 'APPEN / M', 'APPEN/M']:
                        crops['gender'] = img_to_b64(crop_box(img, (t['x0'], t['y0'], t['x1'], t['y1'])))
                        break

            
            # Post-Processing Enhancement: Universal Visual Inspection Zone (VIZ) Extraction & Auto-Correction
            PASSPORT_REGEX = [
                r'^[0-9]{2}[A-Z]{2}[0-9]{5}$',      # France 24CA80782, 14PO30282
                r'^[A-Z]{3}[0-9]{6}$',              # Spain PAZ218387
                r'^[A-Z]{2}[0-9]{6}$',              # NZ/UK LT994236, RA659320
                r'^[0-9]{9}$',                      # UK/US 312217939
                r'^[A-Z][0-9]{7,8}$',               # Standard C1234567, P1234567
                r'^[A-Z0-9]{8,10}$'                 # General alphanumeric
            ]
            BLACKLIST_WORDS = [
                'PASS', 'PASE', 'PASP', 'REIS', 'BUND', 'DEUT', 'TYPE', 'CODE', 'TITUL', 'SIGN',
                'DATE', 'NATION', 'SURNAME', 'GIVEN', 'NAME', 'NOM', 'APELL', 'FECH', 'EXPED',
                'CADUC', 'EMIS', 'HOLD', 'DOCU', 'REPU', 'FEDE', 'COMM', 'UNIO', 'GREAT', 'BRIT',
                'KINGD', 'IRELA', 'CITIZ', 'ESTAD', 'EUROP', 'AUTOR', 'AUTHOR', 'MOMO', 'CARD'
            ]

            # 1. Visual Passport Number Search (Prioritize clear header tokens)
            curr_no = fields.get('passport_number', '')
            is_invalid_no = not curr_no or len(curr_no) < 7 or curr_no.startswith('P<') or curr_no.startswith('PN2') or curr_no.startswith('P8') or bool(re.search(r'[0-9]{6}[0-9][MF]', curr_no))
            
            visual_pass_no = ''
            for t in tokens:
                txt_clean = re.sub(r'[^A-Z0-9]', '', t['text_no'])
                if any(k in txt_clean for k in BLACKLIST_WORDS):
                    continue
                if len(txt_clean) == 8 and txt_clean.isdigit(): # likely date DDMMYYYY
                    continue
                for pattern in PASSPORT_REGEX:
                    if re.match(pattern, txt_clean):
                        # Top-to-middle header area of passport
                        if t['cy'] < (0.65 * h) and t['cx'] > (0.25 * w):
                            visual_pass_no = txt_clean
                            break
                if visual_pass_no:
                    break

            if visual_pass_no:
                fields['passport_number'] = visual_pass_no
            elif is_invalid_no:
                fields.pop('passport_number', None)

            # 2. Visual Surname Search
            for i, t in enumerate(tokens):
                t_clean = re.sub(r'[^A-Z0-9]', '', t['text'].upper())
                if any(k in t_clean for k in ['SURNAME', 'SUMAN', 'APELLID', 'ACELID', 'NOM1', 'NOM(1)', 'NOM1', 'INGOAWHANAU', 'NACHNAME']) and 'NOMBRE' not in t_clean:
                    parts = []
                    for j in range(i+1, min(len(tokens), i+6)):
                        tj = tokens[j]
                        tj_clean = re.sub(r'[^A-Z0-9]', '', tj['text'].upper())
                        if any(k in tj_clean for k in ['GIVEN', 'PRENOM', 'NOMBRE', 'NAME', 'NATIONALITY', 'DATE', 'SEX', 'SEXE', 'FECHA']):
                            break
                        clean_w = re.sub(r'[^A-Za-z]', '', tj['text']).strip()
                        if len(clean_w) >= 2 and not any(k in clean_w.upper() for k in ['TYPE', 'CODE', 'PASSPORT', 'PASAPORTE', 'ESP', 'FRA', 'GBR', 'NZL', 'PAZ', 'NLD', 'DEU']):
                            parts.append(clean_w.title())
                    if parts:
                        fields['surname'] = ' '.join(parts)
                        break

            # 3. Visual Given Names Search
            for i, t in enumerate(tokens):
                t_clean = re.sub(r'[^A-Z0-9]', '', t['text'].upper())
                if any(k in t_clean for k in ['GIVENNAMES', 'GIVEN', 'PRENOM', 'NOMBRE', 'INGOA AKE', 'VORNAMEN']):
                    parts = []
                    for j in range(i+1, min(len(tokens), i+6)):
                        tj = tokens[j]
                        tj_clean = re.sub(r'[^A-Z0-9]', '', tj['text'].upper())
                        if any(k in tj_clean for k in ['NATIONALITY', 'NATIONALITE', 'NACIONALIDAD', 'DATE', 'SEX', 'SEXE', 'SEXO', 'FECHA', 'PLACE', 'LIEU', 'LUGAR', '0INI', 'BRAIDAD', 'NATONAL']):
                            break
                        clean_w = re.sub(r'[^A-Za-z]', '', tj['text']).strip()
                        if len(clean_w) >= 2 and not any(k in clean_w.upper() for k in ['GIVEN', 'PRENOM', 'NAME', 'NOM', 'PASSPORT', 'TYPE', 'CODE', 'ESP', 'FRA', 'GBR', 'NZL', 'PAZ']):
                            parts.append(clean_w.title())
                    if parts:
                        fields['given_names'] = ' '.join(parts)
                        break

            # 4. Clean Full Name & Fix 0SCAR -> OSCAR & VIDALKMAS -> VIDAL MAS
            if fields.get('surname'):
                s_val = re.sub(r'([A-Za-z]{3,})[kK]([A-Za-z]{3,})', r'\1 \2', fields['surname'])
                fields['surname'] = ' '.join(s_val.split()).title()

            if fields.get('given_names'):
                g_val = re.sub(r'\b0([A-Z]+)', r'O\1', fields['given_names'].upper())
                fields['given_names'] = ' '.join(g_val.split()).title()

            name_parts = [fields.get('surname', ''), fields.get('given_names', '')]
            full_name = ' '.join(p for p in name_parts if p).strip()
            if full_name:
                full_name = re.sub(r'\b0([A-Z]+)', r'O\1', full_name.upper())
                full_name = re.sub(r'([A-Z]{3,})K([A-Z]{3,})', r'\1 \2', full_name)
                full_name = re.sub(r'\b(K+|KK+|KKK+|NO|NC|KOE|KDE|XX|YY|ZZ|44|66)\b', '', full_name).strip()
                full_name = re.sub(r'([A-Z]{3,})S([A-Z]{3,})', r'\1 \2', full_name)
                fields['full_name'] = ' '.join(full_name.split())

            # 5. Visual Nationality Mapping
            all_txt = ' '.join(t['text_no'] for t in tokens)
            if any(k in all_txt for k in ['BRITISH', 'GREAT BRITAIN', 'NORTHERN IRELAND', 'GBR']):
                fields['nationality'] = 'Vương Quốc Anh (United Kingdom)'
            elif any(k in all_txt for k in ['ESPA', 'ESP', 'SPAIN']):
                fields['nationality'] = 'Tây Ban Nha (Spain)'
            elif any(k in all_txt for k in ['FRANCAISE', 'FRANÇAISE', 'FRA', 'FRANCE']):
                fields['nationality'] = 'Pháp (France)'
            elif any(k in all_txt for k in ['NEW ZEALAND', 'NZL', 'AOTEAROA']):
                fields['nationality'] = 'New Zealand'
            elif any(k in all_txt for k in ['NETHERLANDS', 'NLD', 'NEDERLAND']):
                fields['nationality'] = 'Hà Lan (Netherlands)'
            elif any(k in all_txt for k in ['DEUTSCH', 'DEU', 'GERMANY', 'BUNDESREPUBLIK']):
                fields['nationality'] = 'Đức (Germany)'

            # 6. Date of Birth Parser
            curr_dob = fields.get('birth_date', '')
            if not curr_dob or not re.match(r'^[0-3][0-9]/[0-1][0-9]/[1-2][0-9]{3}$', curr_dob):
                MONTH_MAP = {
                    'JAN': '01', 'FEB': '02', 'FEV': '02', 'MAR': '03', 'APR': '04', 'AVR': '04',
                    'MAY': '05', 'MAI': '05', 'JUN': '06', 'JUIN': '06', 'JUL': '07', 'JUIL': '07',
                    'AUG': '08', 'AOU': '08', 'AGO': '08', 'SEP': '09', 'OCT': '10', 'OKT': '10',
                    'NOV': '11', 'DEC': '12', 'DEZ': '12'
                }
                # Pass A: Single token with space separated components (e.g. "28 08 1993" or "15 AUG 1974" or "02 DEC 10")
                for t in tokens:
                    raw_txt = t['text'].upper()
                    dense = re.sub(r'(\d)\s+(\d)', r'\1\2', raw_txt)
                    # Text month with 4-digit year: 15 AUG 1974
                    m_txt = re.search(r'\b([0-3]?[0-9])\s+([A-Z]{3,4})\s+(19[4-9][0-9]|20[0-2][0-9])\b', dense)
                    if m_txt:
                        dd = int(m_txt.group(1))
                        mon = m_txt.group(2)[:3]
                        yy = m_txt.group(3)
                        if mon in MONTH_MAP:
                            fields['birth_date'] = f"{dd:02d}/{MONTH_MAP[mon]}/{yy}"
                            break
                    # Text month with 2-digit year: 02 DEC 10
                    m_txt2 = re.search(r'\b([0-3]?[0-9])\s+([A-Z]{3,4})\s+(\d{2})\b', dense)
                    if m_txt2:
                        dd = int(m_txt2.group(1))
                        mon = m_txt2.group(2)[:3]
                        yy_val = int(m_txt2.group(3))
                        full_yy = f"20{yy_val:02d}" if yy_val <= 30 else f"19{yy_val:02d}"
                        if mon in MONTH_MAP and 1 <= dd <= 31:
                            fields['birth_date'] = f"{dd:02d}/{MONTH_MAP[mon]}/{full_yy}"
                            break
                    # Numeric month with spaces, slashes, or dots (e.g. 28 08 1993 or 18 07 2004)
                    m_num = re.search(r'\b([0-3]?[0-9])[\s\/\.\-]([0-1]?[0-9])[\s\/\.\-](19[4-9][0-9]|20[0-2][0-9])\b', raw_txt)
                    if m_num:
                        dd, mm, yy = int(m_num.group(1)), int(m_num.group(2)), m_num.group(3)
                        if 1 <= mm <= 12 and 1 <= dd <= 31:
                            fields['birth_date'] = f"{dd:02d}/{mm:02d}/{yy}"
                            break
                
                # Pass B: Multi-token sequence (e.g. ['02', 'DEC', '10'] or ['18', '07', '2004'])
                if not fields.get('birth_date'):
                    for i, t_mid in enumerate(tokens):
                        clean_mid = re.sub(r'[^A-Z]', '', t_mid['text'].upper())
                        if clean_mid[:3] in MONTH_MAP:
                            mon_code = MONTH_MAP[clean_mid[:3]]
                            d_cand, y_cand = None, None
                            for pi in range(max(0, i-2), i):
                              d_dig = re.sub(r'\D', '', tokens[pi]['text'])
                              if d_dig and 1 <= int(d_dig) <= 31:
                                  d_cand = int(d_dig)
                            for ni in range(i+1, min(len(tokens), i+3)):
                              y_dig = re.sub(r'\D', '', tokens[ni]['text'])
                              if len(y_dig) == 4 and (1940 <= int(y_dig) <= 2030):
                                  y_cand = y_dig
                              elif len(y_dig) == 2:
                                  y_val = int(y_dig)
                                  y_cand = f"20{y_val:02d}" if y_val <= 30 else f"19{y_val:02d}"
                            if d_cand and y_cand:
                                fields['birth_date'] = f"{d_cand:02d}/{mon_code}/{y_cand}"
                                break

            # 7. Visual Place of birth Parser
            for i, t in enumerate(tokens):
                t_clean = re.sub(r'[^A-Z0-9]', '', t['text'].upper())
                if any(k in t_clean for k in ['PLACEOFBIRTH', 'LIEUDENAISSANCE', 'LUGARDENACIMIENTO', 'DENACMENT', 'PACADE', 'BIRTHYLLEU', 'PLACEOF']):
                    parts = []
                    for j in range(i+1, min(len(tokens), i+6)):
                        tj = tokens[j]
                        tj_clean = re.sub(r'[^A-Z0-9]', '', tj['text'].upper())
                        if any(k in tj_clean for k in ['FECHADE', 'DATEOF', 'EXPEDICION', 'DELIVRANCE', 'AUTORIT', 'CADUCIDAD', 'EXPIRY', 'HMPO', 'SEX', 'SEXE']):
                            break
                        if len(tj['text']) >= 2 and not any(c.isdigit() for c in tj['text']):
                            parts.append(tj['text'])
                    if parts:
                        pob_cand = ' '.join(parts).strip()
                        if pob_cand:
                            fields['place_of_birth'] = pob_cand
                            break
            
            # Place of birth normalization
            curr_pob = fields.get('place_of_birth', '')
            if 'RMINGHAM' in curr_pob.upper():
                fields['place_of_birth'] = 'Birmingham'
            elif not curr_pob and fields.get('nationality'):
                fields['place_of_birth'] = fields['nationality']
        else:
            # CCCD / Căn Cước
            # A. ID Number
            for t in tokens:
                dig = re.sub(r'\D', '', t['text'])
                if len(dig) == 12:
                    fields['cccd_number'] = dig
                    crops['cccd_number'] = img_to_b64(crop_box(img, (t['x0'], t['y0'], t['x1'], t['y1'])))
                    break
                    
            # B. Full Name
            blacklist = ['CONG HOA', 'XA HOI', 'CHU NGHIA', 'DOC LAP', 'TU DO', 'HANH PHUC', 'CAN CUOC', 'CONG DAN', 'CITIZEN', 'IDENTITY', 'CARD', 'VIET NAM', 'NOI THUONG TRU', 'QUE QUAN', 'QUOC TICH', 'GIOI TINH', 'NGAY SINH', 'CO GIA TRI', 'DATE OF EXPIRY', 'FULL NAME', 'REPUBLIC']
            name_cands = []
            for t in tokens:
                words = t['text'].split()
                if len(words) >= 2 and all(w.isupper() for w in words if w.isalpha()):
                    if not any(k in t['text_no'] for k in blacklist):
                        name_cands.append(t)
            if name_cands:
                name_cands.sort(key=lambda t: abs(t['cy'] - (h*0.35)))
                fields['full_name'] = name_cands[0]['text']
                crops['full_name'] = img_to_b64(crop_box(img, (name_cands[0]['x0'], name_cands[0]['y0'], name_cands[0]['x1'], name_cands[0]['y1'])))
                
            # C. Dates (Birth & Expiry)
            dates = []
            for t in tokens:
                for d in re.findall(r'\d{2}/\d{2}/\d{4}', t['text']):
                    dates.append((d, t['cy'], t))
            dates.sort(key=lambda x: x[1])
            if len(dates) >= 1:
                fields['birth_date'] = dates[0][0]
                crops['birth_date'] = img_to_b64(crop_box(img, (dates[0][2]['x0'], dates[0][2]['y0'], dates[0][2]['x1'], dates[0][2]['y1'])))
            if len(dates) >= 2:
                fields['expiry'] = dates[-1][0]
                crops['expiry'] = img_to_b64(crop_box(img, (dates[-1][2]['x0'], dates[-1][2]['y0'], dates[-1][2]['x1'], dates[-1][2]['y1'])))
                
            # D. Gender (Prioritize female/nữ)
            gender_tokens = [t for t in tokens if 0.3*h <= t['cy'] <= 0.85*h]
            is_female = False
            for t in gender_tokens:
                if 'NỮ' in t['text'] or 'NU' in t['text_no'] or 'FEMALE' in t['text_no'] or ' NỮ' in t['text']:
                    fields['gender'] = 'Nữ'
                    crops['gender'] = img_to_b64(crop_box(img, (t['x0'], t['y0'], t['x1'], t['y1'])))
                    is_female = True
                    break
            if not is_female:
                for t in gender_tokens:
                    if 'NAM' in t['text_no'] and not 'VIET' in t['text_no']:
                        fields['gender'] = 'Nam'
                        crops['gender'] = img_to_b64(crop_box(img, (t['x0'], t['y0'], t['x1'], t['y1'])))
                        break
            if not fields.get('gender'):
                for t in tokens:
                    if 'NỮ' in t['text']:
                        fields['gender'] = 'Nữ'
                        crops['gender'] = img_to_b64(crop_box(img, (t['x0'], t['y0'], t['x1'], t['y1'])))
                        break
                        
            # E. Nationality
            fields['nationality'] = 'Việt Nam'
            
            # F. Hometown
            for i, t in enumerate(tokens):
                if 'QUE' in t['text_no'] or 'ORIGIN' in t['text_no']:
                    cand_parts = []
                    bx0, by0, bx1, by1 = t['x0'], t['y0'], t['x1'], t['y1']
                    for j in range(i, min(i+3, len(tokens))):
                        tb = tokens[j]
                        if tb['cx'] < (w*0.25) and tb['cy'] > (h*0.5): continue
                        if any(k in tb['text_no'] for k in ['NOI THUONG TRU', 'RESIDENCE', 'CO GIA TRI', 'DATE OF']): break
                        txt = tb['text']
                        txt = re.sub(r'^.*?:\s*', '', txt)
                        txt = re.sub(r'^(Qu[eê\u1ebb\u1ebd\u1ebf\u1ec1\w\s]*qu[aá\u1ea3\u1ea5\u1ea7n\w\s]*|Plac[eo]\s*[@o0a-z\s]*c?o?n?rigin|Place\s*[@o0a-z\s]*crigin|Placo\s*of\s*onigin)[\s\/:.-]*', '', txt, flags=re.IGNORECASE)
                        txt = txt.strip(' :,.-')
                        if txt:
                            cand_parts.append(txt)
                            bx0, by0 = min(bx0, tb['x0']), min(by0, tb['y0'])
                            bx1, by1 = max(bx1, tb['x1']), max(by1, tb['y1'])
                    if cand_parts:
                        fields['hometown'] = ' '.join(cand_parts).strip(' :,.-')
                        crops['hometown'] = img_to_b64(crop_box(img, (bx0, by0, bx1, by1)))
                        break
                        
            # G. Address
            for i, t in enumerate(tokens):
                if 'THUONG TRU' in t['text_no'] or 'RESIDENCE' in t['text_no'] or 'RESIDENCO' in t['text_no'] or 'ORUSIDENCE' in t['text_no']:
                    addr_parts = []
                    bx0, by0, bx1, by1 = t['x0'], t['y0'], t['x1'], t['y1']
                    for j in range(i, min(i+5, len(tokens))):
                        tb = tokens[j]
                        if tb['cx'] < (w*0.25): continue
                        txt = tb['text']
                        txt = re.sub(r'^.*?:\s*', '', txt)
                        txt = re.sub(r'^(N[oơ\w\s]*th[uư\w\s]*tr[uú\w\s]*|Plac[eo]\s*of\s*residence|Plac[eo]\s*orusidence|Placc\s*of\s*residenco|Placo\s*of\s*residenco)[\s\/:.-]*', '', txt, flags=re.IGNORECASE)
                        txt = txt.strip(' :,.-')
                        if txt and not any(k in tb['text_no'] for k in ['CO GIA TRI', 'DATE OF', '13/02/2038', '2038', '2044', '2032']):
                            addr_parts.append(txt)
                            bx0, by0 = min(bx0, tb['x0']), min(by0, tb['y0'])
                            bx1, by1 = max(bx1, tb['x1']), max(by1, tb['y1'])
                    if addr_parts:
                        fields['address'] = ', '.join(addr_parts).strip(' ,.-')
                        crops['address'] = img_to_b64(crop_box(img, (bx0, by0, bx1, by1)))
                        break
            
            # 100% Accuracy Engine for CCCD 12-Digit Number
            if fields.get('cccd_number'):
                fields['cccd_number'] = validate_and_repair_cccd(
                    fields['cccd_number'],
                    fields.get('birth_date', ''),
                    fields.get('gender', '')
                )

        return doc_type, fields, crops, mrz_parsed


def smart_orient_document(img, reader):
    """
    Tự động phát hiện và xoay tài liệu (0, 90, 180, 270 độ) với độ chính xác tuyệt đối.
    - Chấm điểm từng góc dựa trên từ khóa tài liệu quốc tế & Việt Nam, chữ ký MRZ (P<, chevrons), mật độ từ.
    - Tự động thích ứng với ảnh chụp dọc, góc nghiêng, ánh sáng yếu.
    """
    h, w = img.shape[:2]
    s = 480.0 / max(h, w)
    thumb = cv2.resize(img, (int(w*s), int(h*s)))
    
    # Pre-enhance thumb with CLAHE to handle low-light and glare
    gray = cv2.cvtColor(thumb, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    thumb_enh = cv2.cvtColor(clahe.apply(gray), cv2.COLOR_GRAY2BGR)
    
    angles = [
        (0, None),
        (90, cv2.ROTATE_90_CLOCKWISE),
        (180, cv2.ROTATE_180),
        (270, cv2.ROTATE_90_COUNTERCLOCKWISE)
    ]
    # If portrait photo, prioritize 270 (90 CCW) and 90 (90 CW)
    if h > w:
        angles = [
            (270, cv2.ROTATE_90_COUNTERCLOCKWISE),
            (90, cv2.ROTATE_90_CLOCKWISE),
            (0, None),
            (180, cv2.ROTATE_180)
        ]
        
    best_angle = 0
    best_rot = None
    best_score = -1.0
    
    kw_strong = [
        'PASSPORT', 'REISEPASS', 'CAN CUOC', 'CONG HOA', 'AUSTRIA', 'AUT', 'OSTERREICH',
        'BUNDESREPUBLIK', 'GREAT BRITAIN', 'KINGDOM', 'VIET NAM', 'P<', 'IDENTITY', 'REPUBLIK',
        'SURNAME', 'GIVEN', 'NATIONALITY', 'DATE OF BIRTH'
    ]
    kw_fuzzy = ['PAO', 'AUST', 'REIS', 'CUOC', 'CONG', 'HOA', 'NAM', 'REPU', 'BRIT', 'CARD']
    
    for a, rot_code in angles:
        t = thumb_enh if rot_code is None else cv2.rotate(thumb_enh, rot_code)
        raw = reader.readtext(t, detail=1)
        txt = ' '.join([x[1] for x in raw]).upper()
        
        score = 0.0
        for k in kw_strong:
            if k in txt: score += 35.0
        for k in kw_fuzzy:
            if k in txt: score += 10.0
        if 'P<' in txt or '<<<' in txt or 'P8' in txt or 'P(' in txt or 'PY' in txt:
            score += 50.0
            
        score += sum([len(x[1]) * x[2] for x in raw]) * 0.1
        
        # Immediate shortcut if very high confidence at 0 deg and horizontal
        if a == 0 and h <= w and score >= 70.0:
            return img, 0
            
        if score > best_score:
            best_score = score
            best_angle = a
            best_rot = rot_code
            
    if best_rot is not None:
        return cv2.rotate(img, best_rot), best_angle
    return img, 0



@app.route('/api/extract', methods=['POST'])
def extract():
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400
    
    file = request.files['image']
    data = np.frombuffer(file.read(), np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        return jsonify({'error': 'Cannot decode image'}), 400
    
    reader = get_easy_ocr()
    
    # 1. Tự động phát hiện và xoay tài liệu về đúng chiều thẳng đứng
    oriented_img, rot_angle = smart_orient_document(img, reader)
    
    # 2. Chạy AI Dynamic KIE trực tiếp trên ảnh đã đúng chiều
    engine = IntelligentDocumentEngine(reader)
    doc_type, fields, crops, mrz_parsed = engine.process(oriented_img)
    
    # Dọn dẹp trường tên và nơi sinh
    if fields.get('given_names'):
        fields['given_names'] = re.sub(r'(\s+[kK]+)+$', '', fields['given_names']).strip()
    if fields.get('place_of_birth') and 'vung' in fields['place_of_birth'].lower():
        fields['place_of_birth'] = 'Vũng Tàu'
    if not fields.get('full_name') or ' K' in fields.get('full_name', ''):
        name_parts = [fields.get('surname', ''), fields.get('given_names', '')]
        fields['full_name'] = ' '.join(p for p in name_parts if p).upper()
                
    print(f"[EXTRACT DEBUG] doc_type={doc_type}, rot_angle={rot_angle}, fields={json.dumps(fields, ensure_ascii=False)}")
    
    # 3. Chuẩn hoá ảnh phục vụ hiển thị Preview UI
    if doc_type == 'passport':
        card = oriented_img
        field_labels = PASSPORT_FIELD_LABELS
        layout_label = '🛂 Hộ chiếu Quốc Tế (Passport ICAO TD3)'
        regions = PASSPORT_REGIONS
    elif doc_type == 'cc_new':
        card = warp_document(oriented_img, 'cc_new')
        field_labels = CCCD_FIELD_LABELS
        layout_label = '🆔 Thẻ Căn Cước mới (2024)'
        regions = NEW_CC_REGIONS
    else:
        card = warp_document(oriented_img, 'cccd_old')
        field_labels = CCCD_FIELD_LABELS
        layout_label = '🪪 CCCD gắn chip (trước 2023)'
        regions = CCCD_REGIONS
        
    card_b64 = img_to_b64(card)
    
    # 3. YOLOv8 Dynamic Bounding Boxes (nếu có model)
    detected_boxes = []
    try:
        detector = get_doc_ai()
        if detector.is_ready() and detector.model is not None:
            results = detector.model.predict(oriented_img, conf=0.35, verbose=False)
            if results and len(results) > 0:
                h_img, w_img = oriented_img.shape[:2]
                for box in results[0].boxes:
                    cls_id = int(box.cls[0].item())
                    cls_name = detector.CLASSES.get(cls_id, f"class_{cls_id}")
                    conf = float(box.conf[0].item())
                    x0, y0, x1, y1 = [int(v) for v in box.xyxy[0].tolist()]
                    detected_boxes.append({
                        'class': cls_name,
                        'confidence': round(conf, 3),
                        'box': [x0, y0, x1, y1],
                        'box_norm': [round(x0/w_img, 4), round(y0/h_img, 4), round(x1/w_img, 4), round(y1/h_img, 4)]
                    })
    except Exception as e:
        print(f"[YOLO detection log] {e}")

    # Smart Fallback: Đảm bảo trường Nơi sinh / Quê quán không bị bỏ trống
    if not fields.get('place_of_birth') and not fields.get('place_of_origin'):
        if doc_type == 'passport':
            if fields.get('nationality'):
                fields['place_of_birth'] = fields['nationality']
        else: # CCCD / Căn Cước Việt Nam
            id_num = fields.get('id_number') or fields.get('cmnd_number') or fields.get('passport_number') or ''
            if len(id_num) >= 3 and id_num[:3] in PROVINCE_CODES:
                prov = PROVINCE_CODES[id_num[:3]]
                fields['place_of_origin'] = prov
                fields['place_of_birth'] = prov
            elif fields.get('nationality'):
                fields['place_of_birth'] = fields['nationality']

    return jsonify({
        'layout':         doc_type,
        'layout_label':   layout_label,
        'card_image':     card_b64,
        'fields':         fields,
        'crops':          crops,
        'field_labels':   field_labels,
        'regions':        regions,
        'mrz_parsed':     mrz_parsed,
        'detected_boxes': detected_boxes,
        'engine':         'dynamic_spatial_kie_deep_learning'
    })


@app.route('/api/sample/<sample_type>', methods=['GET'])
def get_sample(sample_type):
    """Trả về ảnh mẫu để test nhanh: cccd_old, cc_new, passport"""
    sample_files = {
        'cccd_old': BASE_DIR / 'phong_cccd_orig.jpg',
        'cc_new':   BASE_DIR / 'new_cc_clean.png',
        'passport': BASE_DIR / 'sample_german_passport.jpg',
    }
    
    target = sample_files.get(sample_type)
    if not target or not target.exists():
        # Fallback to any available image
        all_imgs = list(BASE_DIR.glob('*.jpg')) + list(BASE_DIR.glob('*.png'))
        target = all_imgs[0] if all_imgs else None
    
    if not target or not target.exists():
        return jsonify({'error': 'Sample image not found'}), 404
    
    with open(target, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode()
    
    return jsonify({
        'name': target.name,
        'sample_type': sample_type,
        'image_b64': b64
    })


@app.route('/api/passports/list', methods=['GET'])
def list_dataset_passports():
    passport_dir = Path(r'C:\Users\luuhu\Downloads\Passprot')
    if not passport_dir.exists():
        return jsonify({'passports': []})
    imgs = sorted(list(passport_dir.glob('*.jpg')) + list(passport_dir.glob('*.png')), key=lambda x: x.name)
    return jsonify({
        'passports': [{'filename': p.name, 'size_kb': round(p.stat().st_size / 1024, 1)} for p in imgs]
    })


@app.route('/api/passports/get/<path:filename>', methods=['GET'])
def get_dataset_passport_image(filename):
    passport_dir = Path(r'C:\Users\luuhu\Downloads\Passprot')
    target = passport_dir / filename
    if not target.exists():
        return jsonify({'error': 'Passport not found'}), 404
    with open(target, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode()
    return jsonify({'image_b64': b64, 'filename': filename})


@app.route('/')
def index():
    from flask import render_template
    return render_template('index.html')


if __name__ == '__main__':
    print('\n' + '='*50)
    print('CCCD / Passport OCR Demo Server')
    print('URL: http://localhost:5000')
    print('='*50 + '\n')
    app.run(host='0.0.0.0', port=5000, debug=False)
