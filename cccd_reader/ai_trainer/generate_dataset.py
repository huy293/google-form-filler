import os, random, re
import cv2
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / 'dataset'

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

# Random sample data pools
HO_LIST = ['NGUYỄN', 'TRẦN', 'LÊ', 'PHẠM', 'HOÀNG', 'HUỲNH', 'PHAN', 'VŨ', 'VÕ', 'ĐẶNG', 'BÙI', 'ĐỖ', 'HỒ', 'NGÔ', 'DƯƠNG']
DEM_LIST = ['VĂN', 'THỊ', 'ĐỨC', 'QUỐC', 'MINH', 'HỮU', 'THANH', 'ANH', 'TIẾN', 'HOÀNG', 'XUÂN', 'KIM']
TEN_LIST = ['NAM', 'HÙNG', 'DŨNG', 'PHONG', 'LONG', 'LINH', 'HƯƠNG', 'TRANG', 'THẢO', 'MAI', 'LAN', 'TUẤN', 'ĐẠT', 'KHOA']

PROVINCE_CODES = {
    '001': 'Hà Nội', '079': 'TP Hồ Chí Minh', '048': 'Đà Nẵng', '031': 'Hải Phòng',
    '092': 'Cần Thơ', '074': 'Bình Dương', '042': 'Hà Tĩnh', '040': 'Nghệ An',
    '038': 'Thanh Hóa', '060': 'Bình Thuận', '044': 'Quảng Bình', '033': 'Hưng Yên'
}

COMMUNES = ['Tân Lâm Hương', 'Tân Hưng', 'Thạch Hà', 'Ngọc Hà', 'Phường Bến Nghé', 'Phường 1', 'Xã An Phú', 'Phường Dịch Vọng']
DISTRICTS = ['Thạch Hà', 'Bàu Bàng', 'Ba Đình', 'Quận 1', 'Cầu Giấy', 'Quận 7', 'Thủ Đức', 'Gia Lâm']
PROVINCES = ['Hà Nội', 'TP Hồ Chí Minh', 'Hà Tĩnh', 'Nghệ An', 'Bình Dương', 'Đà Nẵng', 'Hải Phòng']

FOREIGN_SURNAMES = ['SMITH', 'JOHNSON', 'WILLIAMS', 'BROWN', 'JONES', 'GARCIA', 'MILLER', 'DAVIS', 'LIPERIS', 'MUELLER', 'DUBOIS']
FOREIGN_GIVENS = ['JAMES', 'MARY', 'JOHN', 'PATRICIA', 'ROBERT', 'JENNIFER', 'MICHAEL', 'LINDA', 'ANDREW CHRISTOPHER', 'DAVID']
COUNTRIES = ['GBR', 'USA', 'FRA', 'DEU', 'JPN', 'KOR', 'AUS', 'CAN', 'SGP', 'VNM']


def random_date(start_year=1960, end_year=2006):
    d = random.randint(1, 28)
    m = random.randint(1, 12)
    y = random.randint(start_year, end_year)
    return f"{d:02d}/{m:02d}/{y}"


def random_cccd_number(pcode, is_male, birth_year):
    century = birth_year // 100
    if century == 19:
        gender_digit = 0 if is_male else 1
    elif century == 20:
        gender_digit = 2 if is_male else 3
    else:
        gender_digit = 0
    yy = birth_year % 100
    rand6 = random.randint(100000, 999999)
    return f"{pcode}{gender_digit}{yy:02d}{rand6}"


def get_font(size=22, bold=False):
    font_paths = [
        'C:/Windows/Fonts/arialbd.ttf' if bold else 'C:/Windows/Fonts/arial.ttf',
        'C:/Windows/Fonts/segoeuib.ttf' if bold else 'C:/Windows/Fonts/segoeui.ttf',
        'C:/Windows/Fonts/tahoma.ttf',
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except:
                pass
    return ImageFont.load_default()


def render_synthetic_cccd(doc_type='cccd_old'):
    """Vẽ ảnh thẻ CCCD/Căn cước chuẩn 900x568 với các bounding box tương ứng"""
    w, h = 900, 568
    
    if doc_type == 'cccd_old':
        bg_color = (random.randint(220, 235), random.randint(235, 245), random.randint(240, 250))
    else:
        bg_color = (random.randint(230, 245), random.randint(240, 250), random.randint(245, 255))
        
    img_pil = Image.new('RGB', (w, h), color=bg_color)
    draw = ImageDraw.Draw(img_pil)
    
    font_header_bold = get_font(20, bold=True)
    font_header_sub = get_font(16, bold=True)
    font_title = get_font(24, bold=True)
    font_field_label = get_font(15, bold=False)
    font_field_val = get_font(20, bold=True)
    font_id_num = get_font(30, bold=True)
    
    draw.text((280, 25), "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", fill=(180, 20, 20), font=font_header_bold)
    draw.text((360, 52), "Độc lập - Tự do - Hạnh phúc", fill=(20, 20, 20), font=font_header_sub)
    
    if doc_type == 'cccd_old':
        draw.text((320, 95), "CĂN CƯỚC CÔNG DÂN", fill=(180, 20, 20), font=font_title)
        draw.text((385, 128), "Identity Card", fill=(40, 40, 40), font=font_field_label)
    else:
        draw.text((390, 95), "CĂN CƯỚC", fill=(180, 20, 20), font=font_title)
        draw.text((415, 128), "Identity Card", fill=(40, 40, 40), font=font_field_label)
        
    # Avatar placeholder
    avatar_box = (35, 160, 215, 410)
    draw.rectangle(avatar_box, fill=(180, 195, 210), outline=(120, 130, 140), width=2)
    draw.text((85, 270), "AVATAR", fill=(100, 110, 120), font=font_field_label)
    
    # Data generation
    pcode = random.choice(list(PROVINCE_CODES.keys()))
    is_male = random.choice([True, False])
    gender_str = "Nam" if is_male else "Nữ"
    byear = random.randint(1965, 2005)
    dob_str = random_date(byear, byear)
    id_num = random_cccd_number(pcode, is_male, byear)
    
    ho = random.choice(HO_LIST)
    dem = random.choice(DEM_LIST)
    ten = random.choice(TEN_LIST)
    full_name = f"{ho} {dem} {ten}"
    
    hometown = f"{random.choice(COMMUNES)}, {random.choice(DISTRICTS)}, {random.choice(PROVINCES)}"
    address = f"Số {random.randint(1,199)} {random.choice(COMMUNES)}, {random.choice(DISTRICTS)}, {random.choice(PROVINCES)}"
    expiry_str = f"25/02/{byear + random.choice([25, 40, 60])}"
    
    boxes = []
    boxes.append((9, avatar_box[0], avatar_box[1], avatar_box[2], avatar_box[3])) # Avatar
    
    if doc_type == 'cccd_old':
        # Số CCCD
        draw.text((310, 175), "Số / No.:", fill=(180, 20, 20), font=font_field_label)
        draw.text((400, 165), id_num, fill=(180, 20, 20), font=font_id_num)
        boxes.append((0, 395, 162, 730, 208)) # id_number
        
        # Họ và tên
        draw.text((250, 225), "Họ và tên / Full name:", fill=(50, 50, 50), font=font_field_label)
        draw.text((250, 250), full_name, fill=(10, 10, 10), font=font_field_val)
        boxes.append((1, 245, 246, 750, 285)) # full_name
        
        # Ngày sinh
        draw.text((250, 298), "Ngày sinh / Date of birth:", fill=(50, 50, 50), font=font_field_label)
        draw.text((470, 296), dob_str, fill=(10, 10, 10), font=font_field_val)
        boxes.append((2, 465, 292, 605, 326)) # birth_date
        
        # Giới tính & Quốc tịch
        draw.text((250, 340), "Giới tính / Sex:", fill=(50, 50, 50), font=font_field_label)
        draw.text((375, 338), gender_str, fill=(10, 10, 10), font=font_field_val)
        boxes.append((3, 370, 334, 440, 368)) # gender
        
        draw.text((490, 340), "Quốc tịch / Nationality:", fill=(50, 50, 50), font=font_field_label)
        draw.text((680, 338), "Việt Nam", fill=(10, 10, 10), font=font_field_val)
        boxes.append((4, 675, 334, 800, 368)) # nationality
        
        # Quê quán
        draw.text((250, 385), "Quê quán / Place of origin:", fill=(50, 50, 50), font=font_field_label)
        draw.text((250, 410), hometown, fill=(10, 10, 10), font=get_font(18, bold=True))
        boxes.append((5, 245, 406, 880, 442)) # hometown
        
        # Nơi thường trú
        draw.text((250, 455), "Nơi thường trú / Place of residence:", fill=(50, 50, 50), font=font_field_label)
        draw.text((250, 480), address, fill=(10, 10, 10), font=get_font(18, bold=True))
        boxes.append((6, 245, 476, 880, 545)) # address
        
        # Hạn dùng
        draw.text((35, 475), "Có giá trị đến / Date of expiry:", fill=(40, 40, 40), font=get_font(11, bold=False))
        draw.text((45, 495), expiry_str, fill=(20, 20, 20), font=get_font(18, bold=True))
        boxes.append((7, 30, 470, 220, 530)) # expiry
    else:
        # Căn cước mới 2024
        draw.text((250, 175), "Số định danh cá nhân / Personal identification number:", fill=(40, 40, 40), font=font_field_label)
        draw.text((250, 200), id_num, fill=(180, 20, 20), font=font_id_num)
        boxes.append((0, 245, 195, 600, 245)) # id_number
        
        draw.text((250, 255), "Họ, chữ đệm và tên / Full name:", fill=(40, 40, 40), font=font_field_label)
        draw.text((250, 280), full_name, fill=(10, 10, 10), font=font_field_val)
        boxes.append((1, 245, 275, 750, 315)) # full_name
        
        draw.text((250, 325), "Ngày sinh / Date of birth:", fill=(40, 40, 40), font=font_field_label)
        draw.text((250, 350), dob_str, fill=(10, 10, 10), font=font_field_val)
        boxes.append((2, 245, 345, 400, 380)) # birth_date
        
        draw.text((450, 325), "Giới tính / Sex:", fill=(40, 40, 40), font=font_field_label)
        draw.text((450, 350), gender_str, fill=(10, 10, 10), font=font_field_val)
        boxes.append((3, 445, 345, 530, 380)) # gender
        
        draw.text((250, 395), "Quốc tịch / Nationality:", fill=(40, 40, 40), font=font_field_label)
        draw.text((250, 420), "Việt Nam", fill=(10, 10, 10), font=font_field_val)
        boxes.append((4, 245, 415, 380, 450)) # nationality
        
        draw.text((250, 465), "Nơi cư trú / Place of residence:", fill=(40, 40, 40), font=font_field_label)
        draw.text((250, 490), address, fill=(10, 10, 10), font=get_font(18, bold=True))
        boxes.append((6, 245, 485, 880, 545)) # address
        
        draw.text((35, 475), "Giá trị đến / Expiry:", fill=(40, 40, 40), font=get_font(11, bold=False))
        draw.text((45, 495), expiry_str, fill=(20, 20, 20), font=get_font(18, bold=True))
        boxes.append((7, 30, 470, 220, 530)) # expiry

    return np.array(img_pil), boxes, (w, h)


def render_synthetic_passport():
    """Vẽ ảnh Hộ Chiếu ICAO TD3 chuẩn 900x634 kèm MRZ 2 dòng"""
    w, h = 900, 634
    bg_color = (random.randint(235, 245), random.randint(235, 245), random.randint(230, 240))
    img_pil = Image.new('RGB', (w, h), color=bg_color)
    draw = ImageDraw.Draw(img_pil)
    
    font_bold = get_font(18, bold=True)
    font_label = get_font(13, bold=False)
    font_val = get_font(19, bold=True)
    font_mrz = get_font(23, bold=True)
    
    # Country & Header
    country_code = random.choice(COUNTRIES)
    pass_num = f"{random.choice(['C', 'B', 'P', 'A', 'G'])}{random.randint(10000000, 99999999)}"
    surname = random.choice(FOREIGN_SURNAMES)
    given_name = random.choice(FOREIGN_GIVENS)
    is_male = random.choice([True, False])
    gender_char = "M" if is_male else "F"
    byear = random.randint(1965, 2003)
    dob_mrz = f"{byear%100:02d}{random.randint(1,12):02d}{random.randint(1,28):02d}"
    dob_visual = f"{dob_mrz[4:6]}/{dob_mrz[2:4]}/19{dob_mrz[0:2]}" if byear < 2000 else f"{dob_mrz[4:6]}/{dob_mrz[2:4]}/20{dob_mrz[0:2]}"
    exp_year = byear + 40
    exp_mrz = f"{exp_year%100:02d}1120"
    exp_visual = f"20/11/{exp_year}"
    
    draw.text((40, 25), f"PASSPORT / PASSEPORT - {country_code}", fill=(10, 10, 10), font=font_bold)
    
    # Avatar
    avatar_box = (40, 80, 240, 360)
    draw.rectangle(avatar_box, fill=(180, 195, 210), outline=(120, 130, 140), width=2)
    draw.text((95, 200), "PHOTO", fill=(100, 110, 120), font=font_label)
    
    boxes = []
    boxes.append((9, avatar_box[0], avatar_box[1], avatar_box[2], avatar_box[3])) # Avatar
    
    # Passport Number
    draw.text((600, 30), "Passport No.", fill=(80, 80, 80), font=font_label)
    draw.text((600, 50), pass_num, fill=(180, 20, 20), font=get_font(24, bold=True))
    boxes.append((0, 595, 45, 850, 85)) # id_number / passport_number
    
    # Surname
    draw.text((270, 85), "Surname / Nom", fill=(80, 80, 80), font=font_label)
    draw.text((270, 105), surname, fill=(10, 10, 10), font=font_val)
    boxes.append((1, 265, 100, 700, 135)) # surname / name
    
    # Given Names
    draw.text((270, 145), "Given Names / Prénoms", fill=(80, 80, 80), font=font_label)
    draw.text((270, 165), given_name, fill=(10, 10, 10), font=font_val)
    
    # Nationality
    draw.text((270, 205), "Nationality / Nationalité", fill=(80, 80, 80), font=font_label)
    draw.text((270, 225), country_code, fill=(10, 10, 10), font=font_val)
    boxes.append((4, 265, 220, 420, 255)) # nationality
    
    # Date of Birth
    draw.text((270, 265), "Date of birth / Date de naissance", fill=(80, 80, 80), font=font_label)
    draw.text((270, 285), dob_visual, fill=(10, 10, 10), font=font_val)
    boxes.append((2, 265, 280, 450, 315)) # birth_date
    
    # Sex
    draw.text((550, 265), "Sex / Sexe", fill=(80, 80, 80), font=font_label)
    draw.text((550, 285), gender_char, fill=(10, 10, 10), font=font_val)
    boxes.append((3, 545, 280, 620, 315)) # gender
    
    # Date of Expiry
    draw.text((270, 325), "Date of expiry / Date d'expiration", fill=(80, 80, 80), font=font_label)
    draw.text((270, 345), exp_visual, fill=(10, 10, 10), font=font_val)
    boxes.append((7, 265, 340, 450, 375)) # expiry
    
    # MRZ 2 Lines
    mrz_name = f"{surname.replace(' ', '<')}<<{given_name.replace(' ', '<')}"
    mrz_l1 = f"P<{country_code}{mrz_name}".ljust(44, '<')[:44]
    mrz_l2 = f"{pass_num}9{country_code}{dob_mrz}8{gender_char}{exp_mrz}4<<<<<<<<<<<<<<04".ljust(44, '<')[:44]
    
    # MRZ Zone
    draw.text((40, 475), mrz_l1, fill=(10, 10, 10), font=font_mrz)
    draw.text((40, 520), mrz_l2, fill=(10, 10, 10), font=font_mrz)
    boxes.append((8, 30, 460, 875, 565)) # mrz_zone
    
    return np.array(img_pil), boxes, (w, h)


def apply_photorealistic_augmentation(img, boxes, orig_wh):
    """Thêm nhiễu thực tế: góc xoay, phối cảnh 3D, bóng tối, lóa sáng, viền bàn"""
    w, h = orig_wh
    
    # 1. Đặt thẻ lên mặt bàn nền gỗ/vải/đá ngẫu nhiên
    canvas_w, canvas_h = 1100, 800
    canvas_color = (random.randint(60, 140), random.randint(50, 120), random.randint(40, 100))
    canvas = np.full((canvas_h, canvas_w, 3), canvas_color, dtype=np.uint8)
    
    # Tạo vân gỗ/noise nhẹ trên nền
    noise = np.random.randint(-15, 15, (canvas_h, canvas_w, 3), dtype=np.int16)
    canvas = np.clip(canvas.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    
    # 2. Phối cảnh Homography (Perspective tilt)
    src_pts = np.float32([[0,0], [w,0], [w,h], [0,h]])
    
    # Dịch tâm
    dx = (canvas_w - w) // 2 + random.randint(-40, 40)
    dy = (canvas_h - h) // 2 + random.randint(-30, 30)
    
    # Thêm biến dạng 4 góc
    jitter = 35
    dst_pts = np.float32([
        [dx + random.randint(-jitter, jitter), dy + random.randint(-jitter, jitter)],
        [dx + w + random.randint(-jitter, jitter), dy + random.randint(-jitter, jitter)],
        [dx + w + random.randint(-jitter, jitter), dy + h + random.randint(-jitter, jitter)],
        [dx + random.randint(-jitter, jitter), dy + h + random.randint(-jitter, jitter)]
    ])
    
    M = cv2.getPerspectiveTransform(src_pts, dst_pts)
    warped_card = cv2.warpPerspective(img, M, (canvas_w, canvas_h))
    
    # Mặt nạ alpha để đè lên nền
    mask = cv2.warpPerspective(np.full((h, w), 255, dtype=np.uint8), M, (canvas_w, canvas_h))
    mask_3ch = cv2.merge([mask, mask, mask]) / 255.0
    
    final_img = (warped_card * mask_3ch + canvas * (1.0 - mask_3ch)).astype(np.uint8)
    
    # 3. Biến đổi bounding box tương ứng sang tọa độ mới
    transformed_boxes = []
    for cls_id, x1, y1, x2, y2 in boxes:
        box_pts = np.float32([[x1, y1], [x2, y1], [x2, y2], [x1, y2]]).reshape(-1, 1, 2)
        trans_pts = cv2.perspectiveTransform(box_pts, M).reshape(-1, 2)
        
        nx1 = float(np.clip(trans_pts[:,0].min(), 0, canvas_w))
        ny1 = float(np.clip(trans_pts[:,1].min(), 0, canvas_h))
        nx2 = float(np.clip(trans_pts[:,0].max(), 0, canvas_w))
        ny2 = float(np.clip(trans_pts[:,1].max(), 0, canvas_h))
        
        if (nx2 - nx1) > 8 and (ny2 - ny1) > 8:
            cx = ((nx1 + nx2) / 2.0) / canvas_w
            cy = ((ny1 + ny2) / 2.0) / canvas_h
            bw = (nx2 - nx1) / canvas_w
            bh = (ny2 - ny1) / canvas_h
            transformed_boxes.append((cls_id, cx, cy, bw, bh))
            
    # 4. Thêm ánh sáng/độ tối nhẹ
    gamma = random.uniform(0.85, 1.25)
    invGamma = 1.0 / gamma
    table = np.array([((i / 255.0) ** invGamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
    final_img = cv2.LUT(final_img, table)
    
    return final_img, transformed_boxes


def generate_full_dataset(num_train=300, num_val=60):
    """Sinh toàn bộ tập dataset train & val đa dạng cho CCCD & Passport"""
    for split in ['train', 'val']:
        os.makedirs(DATASET_DIR / 'images' / split, exist_ok=True)
        os.makedirs(DATASET_DIR / 'labels' / split, exist_ok=True)
        
    counts = {'train': num_train, 'val': num_val}
    
    print(f"[GEN] Starting dataset generation: {num_train} train, {num_val} val samples...")
    for split, n in counts.items():
        for i in range(n):
            doc_choice = random.choice(['cccd_old', 'cc_new', 'passport'])
            if doc_choice == 'passport':
                raw_img, boxes, wh = render_synthetic_passport()
            else:
                raw_img, boxes, wh = render_synthetic_cccd(doc_choice)
                
            aug_img, yolo_boxes = apply_photorealistic_augmentation(raw_img, boxes, wh)
            
            img_name = f"{doc_choice}_{split}_{i:04d}.jpg"
            lbl_name = f"{doc_choice}_{split}_{i:04d}.txt"
            
            img_path = DATASET_DIR / 'images' / split / img_name
            lbl_path = DATASET_DIR / 'labels' / split / lbl_name
            
            cv2.imwrite(str(img_path), aug_img, [cv2.IMWRITE_JPEG_QUALITY, random.randint(85, 98)])
            
            with open(lbl_path, 'w', encoding='utf-8') as f:
                for cls_id, cx, cy, bw, bh in yolo_boxes:
                    f.write(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
                    
        print(f"[OK] Generated {n} {split} samples")

    # Tạo data.yaml cho YOLOv8
    yaml_content = f"""path: {str(DATASET_DIR).replace(chr(92), '/')}
train: images/train
val: images/val

names:
  0: id_number
  1: full_name
  2: birth_date
  3: gender
  4: nationality
  5: hometown
  6: address
  7: expiry
  8: mrz_zone
  9: avatar
"""
    with open(DATASET_DIR / 'data.yaml', 'w', encoding='utf-8') as f:
        f.write(yaml_content)
    print(f"[OK] Saved data.yaml configuration")


if __name__ == '__main__':
    generate_full_dataset(num_train=250, num_val=50)
