import os, sys, re, cv2, base64
import numpy as np
from pathlib import Path
from ultralytics import YOLO

BASE_DIR = Path(__file__).resolve().parent

CLASSES = [
    'id_number',    # 0
    'full_name',    # 1
    'birth_date',   # 2
    'gender',       # 3
    'nationality',  # 4
    'hometown',     # 5
    'address',      # 6
    'expiry',       # 7
    'mrz_zone',     # 8
    'avatar',       # 9
]

LABEL_NAMES = {
    'id_number':    'Số CCCD / Hộ chiếu',
    'full_name':    'Họ và tên',
    'birth_date':   'Ngày sinh',
    'gender':       'Giới tính',
    'nationality':  'Quốc tịch',
    'hometown':     'Quê quán',
    'address':      'Nơi thường trú',
    'expiry':       'Có giá trị đến',
    'avatar':       'Ảnh chân dung',
    'mrz_zone':     'Khu vực MRZ (Passport)'
}


def img_to_b64(img_bgr):
    if img_bgr is None or img_bgr.size == 0:
        return ''
    _, buf = cv2.imencode('.jpg', img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return base64.b64encode(buf).decode('utf-8')


class DocumentAIDetector:
    def __init__(self, weights_path=None, easy_reader=None):
        if weights_path is None:
            weights_path = BASE_DIR / 'runs' / 'doc_detector_yolov8' / 'weights' / 'best.pt'
            
        self.weights_path = Path(weights_path)
        self.model = None
        self.reader = easy_reader
        
        if self.weights_path.exists():
            print(f"[DocAI] Loading trained YOLOv8 Document model: {self.weights_path}")
            self.model = YOLO(str(self.weights_path))
        else:
            print(f"[DocAI WARN] Weights not found at {self.weights_path}")

    def is_ready(self):
        return self.model is not None

    def ocr_crop(self, crop, field_name):
        if crop is None or crop.size == 0:
            return ''
        if self.reader is None:
            return ''
            
        try:
            res = self.reader.readtext(crop, detail=0, paragraph=False)
            raw_text = ' '.join(res).strip()
            
            if field_name == 'id_number':
                digits = re.sub(r'\D', '', raw_text)
                if len(digits) >= 9:
                    return digits[:12]
                # If passport (letters + digits)
                pass_match = re.search(r'[A-Z]\d{7,8}', raw_text.upper().replace(' ', ''))
                if pass_match:
                    return pass_match.group()
                return raw_text
                
            elif field_name in ('birth_date', 'expiry'):
                m = re.search(r'\d{1,2}[/.-]\d{1,2}[/.-]\d{4}', raw_text)
                if m:
                    return m.group()
                return raw_text
                
            elif field_name == 'gender':
                upper = raw_text.upper()
                if 'NAM' in upper or 'M' == upper or 'MALE' in upper:
                    return 'Nam'
                if 'NỮ' in upper or 'NU' in upper or 'F' == upper or 'FEMALE' in upper:
                    return 'Nữ'
                return raw_text
                
            elif field_name == 'nationality':
                if any(k in raw_text.upper() for k in ['VIỆT', 'VIET', 'VN']):
                    return 'Việt Nam'
                return raw_text
                
            elif field_name == 'full_name':
                # Remove prefixes like 'Họ và tên / Full name'
                cleaned = re.sub(r'^(H[oọ]\s*(v[aà]\s*)?t[eê]n|Full\s*name|Surname|Given\s*names)[\s\/:.-]*', '', raw_text, flags=re.IGNORECASE)
                return cleaned.strip()
                
            elif field_name in ('hometown', 'address'):
                cleaned = re.sub(r'^(Qu[eê]\s*qu[aá]n|Place\s*of\s*origin|N[oơ]i\s*th[uư][oờ]ng\s*tr[uú]|N[oơ]i\s*c[uư]\s*tr[uú]|Place\s*of\s*residence)[\s\/:.-]*', '', raw_text, flags=re.IGNORECASE)
                return cleaned.strip()
                
            return raw_text
        except Exception as e:
            return ''

    def detect_and_extract(self, img_bgr):
        """Chạy mô hình YOLOv8 phát hiện động tất cả các trường trên ảnh"""
        if not self.is_ready():
            return None
            
        h, w = img_bgr.shape[:2]
        results = self.model(img_bgr, conf=0.25, verbose=False)
        
        detected_boxes = []
        fields = {}
        crops = {}
        
        has_mrz = False
        
        if len(results) > 0 and results[0].boxes is not None:
            boxes = results[0].boxes
            for box in boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                x1, y1, x2, y2 = [int(v) for v in box.xyxy[0]]
                
                # Clip to image bounds
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)
                
                if cls_id < len(CLASSES):
                    field_name = CLASSES[cls_id]
                    crop_img = img_bgr[y1:y2, x1:x2]
                    
                    if field_name == 'mrz_zone':
                        has_mrz = True
                        
                    detected_boxes.append({
                        'class_id': cls_id,
                        'field_name': field_name,
                        'label': LABEL_NAMES.get(field_name, field_name),
                        'conf': conf,
                        'box': [x1, y1, x2, y2],
                    })
                    
                    # OCR the cropped field
                    crops[field_name] = img_to_b64(crop_img)
                    if field_name != 'avatar':
                        ocr_val = self.ocr_crop(crop_img, field_name)
                        # Save if not already found or higher confidence
                        if not fields.get(field_name):
                            fields[field_name] = ocr_val

        doc_type = 'passport' if has_mrz else 'cccd'
        layout_label = '🛂 Hộ Chiếu Quốc Tế (YOLOv8 AI)' if doc_type == 'passport' else '🪪 Căn Cước / CCCD (YOLOv8 AI)'
        
        return {
            'doc_type': doc_type,
            'layout_label': layout_label,
            'fields': fields,
            'crops': crops,
            'detected_boxes': detected_boxes,
            'card_image': img_to_b64(img_bgr)
        }
