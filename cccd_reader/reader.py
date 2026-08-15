"""
CCCD Reader - Đọc mặt trước Căn Cước Công Dân Việt Nam
=======================================================
Thuật toán: Classical Computer Vision + Template Matching
KHÔNG dùng AI model có sẵn - tự build từ đầu

Pipeline:
  Ảnh → Tiền xử lý → Phát hiện thẻ → Chỉnh perspective
       → Cắt vùng cố định → Tách ký tự → Template Matching
       → Kết quả JSON
"""

import cv2
import numpy as np
import os
import json


# ─────────────────────────────────────────────
# BƯỚC 1: TIỀN XỬ LÝ ẢNH
# ─────────────────────────────────────────────

def preprocess(image):
    """
    Chuyển ảnh màu → đen trắng sắc nét để dễ xử lý.

    Tại sao làm vậy?
    - Grayscale: bỏ màu, chỉ giữ độ sáng
    - GaussianBlur: làm mịn, khử nhiễu hạt (noise)
    - adaptiveThreshold: tách chữ (trắng) ra khỏi nền (đen)
      dùng "adaptive" vì ánh sáng chụp không đều
    """
    # B1: Chuyển sang ảnh xám (1 kênh thay vì 3 kênh RGB)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # B2: Làm mịn ảnh bằng bộ lọc Gaussian (kernel 5x5)
    # Mỗi pixel = trung bình có trọng số của 25 pixel xung quanh
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # B3: Adaptive Thresholding - phân ngưỡng thích nghi
    # Với mỗi pixel, ngưỡng được tính từ vùng 11x11 xung quanh nó
    # → Tốt hơn global threshold khi ánh sáng không đều
    thresh = cv2.adaptiveThreshold(
        blurred,
        255,                              # Giá trị max (trắng)
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,  # Dùng Gaussian để tính ngưỡng
        cv2.THRESH_BINARY_INV,           # Đảo: chữ = trắng, nền = đen
        11,                              # Kích thước vùng tính ngưỡng
        2                                # Hằng số trừ bớt
    )
    return thresh


# ─────────────────────────────────────────────
# BƯỚC 2: PHÁT HIỆN VÀ CẮT THẺ CCCD
# ─────────────────────────────────────────────

def order_corners(pts):
    """
    Sắp xếp 4 góc theo thứ tự: Top-Left, Top-Right, Bottom-Right, Bottom-Left.

    Ý tưởng:
    - TL: tổng x+y nhỏ nhất
    - BR: tổng x+y lớn nhất
    - TR: hiệu y-x nhỏ nhất
    - BL: hiệu y-x lớn nhất
    """
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]   # Top-Left
    rect[2] = pts[np.argmax(s)]   # Bottom-Right
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)] # Top-Right
    rect[3] = pts[np.argmax(diff)] # Bottom-Left
    return rect


def detect_card(image):
    """
    Phát hiện thẻ CCCD trong ảnh bằng Canny Edge Detection + Contour.

    Ý tưởng:
    1. Canny: tìm các cạnh (viền) trong ảnh
    2. findContours: tìm tất cả đường viền khép kín
    3. Lọc: chọn contour lớn nhất có 4 cạnh (hình chữ nhật = thẻ)
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Canny Edge Detection:
    # - Tính gradient (đạo hàm) của ảnh
    # - Pixel có gradient > 150: chắc chắn là cạnh
    # - Pixel có gradient 50~150: là cạnh nếu kề cạnh chắc chắn
    edges = cv2.Canny(blurred, 50, 150)

    # Giãn nở cạnh để nối các đoạn bị đứt
    kernel = np.ones((3, 3), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=1)

    # Tìm tất cả contour, sắp xếp theo diện tích giảm dần
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    for cnt in contours[:10]:
        # Xấp xỉ contour thành đa giác
        # epsilon = 2% chu vi: cho phép sai lệch nhỏ
        perimeter = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * perimeter, True)

        # Chữ nhật = 4 đỉnh
        if len(approx) == 4:
            return approx.reshape(4, 2)

    return None  # Không tìm thấy thẻ


def perspective_transform(image, corners):
    """
    Chỉnh ảnh thẻ bị nghiêng về dạng phẳng, thẳng.

    Dùng Homography Matrix (ma trận 3x3) để biến đổi phối cảnh.
    CCCD chuẩn: 85.6mm x 54mm → tỉ lệ 1.585 → dùng 856x540 pixel
    """
    rect = order_corners(corners)

    # Kích thước chuẩn đầu ra (pixel)
    W, H = 856, 540
    dst_pts = np.array([
        [0,     0    ],  # Top-Left
        [W - 1, 0    ],  # Top-Right
        [W - 1, H - 1],  # Bottom-Right
        [0,     H - 1],  # Bottom-Left
    ], dtype=np.float32)

    # Tính ma trận Homography: M sao cho dst = M * src
    M = cv2.getPerspectiveTransform(rect, dst_pts)

    # Áp dụng biến đổi
    warped = cv2.warpPerspective(image, M, (W, H))
    return warped


# ─────────────────────────────────────────────
# BƯỚC 3: CẮT VÙNG CỐ ĐỊNH THEO LAYOUT CCCD
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────
# LAYOUT 1: CCCD cũ (Căn Cước Công Dân - trước 2023)
# ─────────────────────────────────────────────────────────────────
# Calibrated bang calib_old.png tren anh CCCD mau 001082946357
CCCD_REGIONS = {
    "cccd_number": (0.30, 0.28, 0.78, 0.40),  # So / No.
    "full_name":   (0.30, 0.40, 0.95, 0.52),  # Ho va ten
    "birth_date":  (0.30, 0.52, 0.68, 0.63),  # Ngay sinh
    "gender":      (0.30, 0.63, 0.52, 0.73),  # Gioi tinh
    "nationality": (0.58, 0.63, 0.95, 0.73),  # Quoc tich
    "hometown":    (0.30, 0.73, 0.95, 0.83),  # Que quan
    "residence":   (0.30, 0.83, 0.95, 0.93),  # Noi thuong tru
    "expiry":      (0.04, 0.86, 0.28, 0.95),  # Han dung
}

# ─────────────────────────────────────────────────────────────────
# LAYOUT 2: Can Cuoc moi (2023+)
# Calibrated bang calib_new.png
# ─────────────────────────────────────────────────────────────────
NEW_CC_REGIONS = {
    # Calibrated tu new_cc_grid.png (900x604)
    "cccd_number": (0.27, 0.43, 0.92, 0.52),  # So dinh danh ca nhan
    "full_name":   (0.27, 0.52, 0.87, 0.62),  # Ho, chu dem va ten / Full name
    "birth_date":  (0.27, 0.62, 0.62, 0.72),  # Ngay, thang, nam sinh
    "gender":      (0.63, 0.62, 0.87, 0.72),  # Gioi tinh (cung hang ngay sinh)
    "nationality": (0.27, 0.72, 0.70, 0.82),  # Quoc tich / Nationality
    "expiry":      (0.03, 0.82, 0.27, 0.92),  # Co gia tri den / Date of expiry
}



def detect_layout(warped_card):
    """
    Phát hiện loại thẻ: CCCD cũ hay Căn Cước mới.
    Dựa vào màu sắc tiêu đề (đỏ = CCCD cũ, hồng = mới)
    hoặc tỉ lệ card.
    """
    h, w = warped_card.shape[:2]
    # Vùng tiêu đề (phần trên giữa)
    title_region = warped_card[int(h*0.18):int(h*0.30), int(w*0.20):int(w*0.80)]

    # Convert sang HSV để phân tích màu
    hsv = cv2.cvtColor(title_region, cv2.COLOR_BGR2HSV)

    # Đỏ đậm (CCCD cũ): H=0-10 hoặc 170-180, S>100, V>100
    mask_red = cv2.inRange(hsv, (0, 100, 100), (10, 255, 255))
    mask_red2 = cv2.inRange(hsv, (170, 100, 100), (180, 255, 255))
    red_pct = (cv2.countNonZero(mask_red) + cv2.countNonZero(mask_red2)) / title_region.size

    # Hồng/đỏ nhạt (Căn Cước mới): H=150-175, S>50
    mask_pink = cv2.inRange(hsv, (140, 50, 100), (175, 255, 255))
    pink_pct = cv2.countNonZero(mask_pink) / title_region.size

    if red_pct > 0.02:
        return "old_cccd", CCCD_REGIONS
    elif pink_pct > 0.01:
        return "new_cc", NEW_CC_REGIONS
    else:
        return "old_cccd", CCCD_REGIONS  # Fallback


def crop_region(warped_card, region_name, regions=None):
    """Cat vung thong tin tu anh the da chinh perspective.
    regions: dict layout (CCCD_REGIONS hoac NEW_CC_REGIONS), mac dinh la CCCD_REGIONS
    """
    if regions is None:
        regions = CCCD_REGIONS
    h, w = warped_card.shape[:2]
    x1_pct, y1_pct, x2_pct, y2_pct = regions[region_name]

    x1 = int(x1_pct * w)
    y1 = int(y1_pct * h)
    x2 = int(x2_pct * w)
    y2 = int(y2_pct * h)

    return warped_card[y1:y2, x1:x2]


# ─────────────────────────────────────────────
# BƯỚC 4: TEMPLATE MATCHING - TỰ BUILD
# ─────────────────────────────────────────────

class TemplateMatchingOCR:
    """
    Nhận dạng chữ số bằng Template Matching.

    Ý tưởng:
    - Có sẵn 10 ảnh mẫu: templates/0.png, 1.png ... 9.png
    - Với mỗi ký tự cần nhận dạng:
        → Resize về cùng kích thước mẫu
        → Tính điểm tương đồng với từng mẫu (0-9)
        → Chọn mẫu có điểm cao nhất
    - Không cần training! Chỉ cần 1 ảnh mẫu mỗi chữ số.

    Hàm tính điểm dùng: TM_CCOEFF_NORMED (tương quan chéo chuẩn hóa)
    Giá trị: -1 (hoàn toàn ngược) → 0 (không liên quan) → 1 (giống hệt)
    """

    def __init__(self, template_dir: str):
        self.templates = {}
        self._load_templates(template_dir)

    def _load_templates(self, template_dir: str):
        """Load ảnh mẫu từ thư mục templates/"""
        for ch in "0123456789":
            path = os.path.join(template_dir, f"{ch}.png")
            if os.path.exists(path):
                img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    self.templates[ch] = img
                    print(f"  Loaded template: '{ch}'")
        print(f"Loaded {len(self.templates)}/10 digit templates.")

    def recognize_digit(self, char_img_gray) -> tuple[str, float]:
        """
        Nhận dạng 1 ký tự bằng Template Matching.
        Returns: (character, confidence_score)
        """
        if not self.templates:
            return "?", 0.0

        best_char = "?"
        best_score = -1.0

        for ch, template in self.templates.items():
            # Resize ảnh cần nhận dạng về đúng kích thước template
            resized = cv2.resize(
                char_img_gray,
                (template.shape[1], template.shape[0])
            )

            # Tính điểm tương đồng
            # TM_CCOEFF_NORMED: (-1, 1), càng gần 1 càng giống
            result = cv2.matchTemplate(resized, template, cv2.TM_CCOEFF_NORMED)
            score = float(result[0][0])

            if score > best_score:
                best_score = score
                best_char = ch

        # Ngưỡng tin cậy: nếu điểm < 0.4 thì không chắc
        if best_score < 0.4:
            return "?", best_score

        return best_char, best_score

    def recognize_line(self, region_img) -> str:
        """
        Nhận dạng 1 dòng chữ số từ ảnh vùng.

        Pipeline:
        1. Tiền xử lý → ảnh nhị phân
        2. Tìm contour từng ký tự
        3. Sắp xếp trái → phải
        4. Nhận dạng từng ký tự
        """
        # Tiền xử lý
        if len(region_img.shape) == 3:
            gray = cv2.cvtColor(region_img, cv2.COLOR_BGR2GRAY)
        else:
            gray = region_img

        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Tìm tất cả contour (vùng pixel trắng liền nhau)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Lọc nhiễu: chỉ giữ contour có kích thước hợp lý
        h_img = thresh.shape[0]
        valid_chars = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            # Chữ số phải đủ cao (>30% chiều cao vùng) và không quá rộng
            if h > h_img * 0.3 and w > 3:
                char_img = thresh[y:y + h, x:x + w]
                valid_chars.append((x, char_img))

        # Sắp xếp trái → phải theo tọa độ x
        valid_chars.sort(key=lambda c: c[0])

        # Nhận dạng từng ký tự
        result = ""
        for _, char_img in valid_chars:
            ch, score = self.recognize_digit(char_img)
            result += ch

        return result


# ─────────────────────────────────────────────
# BƯỚC 5: NHẬN DẠNG GIỚI TÍNH
# ─────────────────────────────────────────────

def detect_gender(gender_region_img) -> str:
    """
    Nhận dạng Nam/Nữ từ vùng giới tính.

    Cách tiếp cận: Pixel Density Heuristic
    - "Nam": 3 ký tự, ít nét hơn
    - "Nữ": 2 ký tự nhưng có dấu phụ (ư, ̃) → nhiều pixel hơn ở 1 vùng nhỏ

    Hoặc: Template Matching với 2 mẫu "Nam" và "Nu"
    → Cái nào match tốt hơn thì đó là giới tính
    """
    gray = cv2.cvtColor(gender_region_img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    h, w = thresh.shape

    # Đếm pixel trắng (chữ) trong từng phần
    # "Nam" và "Nữ" có độ dày nét khác nhau
    total_white = np.sum(thresh > 0)
    area = h * w

    # Mật độ pixel: "Nữ" thường dày đặc hơn do dấu thanh
    density = total_white / area if area > 0 else 0

    # Đây là heuristic đơn giản - cần calibrate bằng ảnh thực
    # Hoàn thiện hơn: dùng Template Matching với 2 ảnh mẫu "Nam", "Nu"
    return "female" if density > 0.35 else "male"


# ─────────────────────────────────────────────
# CLASS CHÍNH: CCCD READER
# ─────────────────────────────────────────────

class CCCDReader:
    """
    Đọc thông tin mặt trước CCCD Việt Nam.
    Hoàn toàn dùng thuật toán, không dùng AI model có sẵn.
    """

    def __init__(self):
        # Đường dẫn thư mục templates (chứa 0.png → 9.png)
        template_dir = os.path.join(os.path.dirname(__file__), "templates")
        os.makedirs(template_dir, exist_ok=True)
        self.ocr = TemplateMatchingOCR(template_dir)

    def read(self, image_path: str) -> dict:
        """
        Đọc thông tin từ ảnh CCCD.

        Args:
            image_path: Đường dẫn ảnh (jpg/png)

        Returns:
            dict với các trường: cccd_number, birth_date, gender, expiry
        """
        print(f"\n Reading: {image_path}")

        # Doc anh
        image = cv2.imread(image_path)
        if image is None:
            return {"error": "Khong doc duoc anh"}

        # Buoc 1: Tien xu ly thong minh (xu ly mo, anh sang, nhieu)
        print("Dang tien xu ly anh...")
        from preprocessing import smart_preprocess
        image, report = smart_preprocess(image, debug=True)
        if report.get("is_blurry"):
            print(f"  Phat hien anh mo (score={report['blur_score_original']}) - da sharpen")

        # Buoc 2: Detect & crop the
        print("Phat hien the CCCD...")

        corners = detect_card(image)
        if corners is not None:
            print("✅ Tìm thấy thẻ, đang chỉnh perspective...")
            card = perspective_transform(image, corners)
        else:
            print("⚠️  Không tìm thấy viền thẻ, dùng ảnh gốc...")
            card = image

        result = {}

        # Bước 3 + 4: Cắt từng vùng và nhận dạng
        print("🔢 Đọc số CCCD...")
        cccd_region = crop_region(card, "cccd_number")
        raw_number = self.ocr.recognize_line(cccd_region)
        # Chỉ giữ chữ số
        result["cccd_number"] = "".join(c for c in raw_number if c.isdigit())

        print("📅 Đọc ngày sinh...")
        birth_region = crop_region(card, "birth_date")
        raw_birth = self.ocr.recognize_line(birth_region)
        result["birth_date"] = raw_birth

        print("👤 Đọc giới tính...")
        gender_region = crop_region(card, "gender")
        result["gender"] = detect_gender(gender_region)

        print("📅 Đọc ngày hết hạn...")
        expiry_region = crop_region(card, "expiry")
        raw_expiry = self.ocr.recognize_line(expiry_region)
        result["expiry"] = raw_expiry

        print(f"\n✅ Kết quả: {json.dumps(result, ensure_ascii=False, indent=2)}")
        return result

    def calibrate(self, image_path: str, save_dir: str = "debug"):
        """
        Debug: Lưu từng vùng cắt ra để kiểm tra tọa độ có đúng không.
        Dùng khi cần điều chỉnh CCCD_REGIONS.
        """
        os.makedirs(save_dir, exist_ok=True)
        image = cv2.imread(image_path)

        corners = detect_card(image)
        card = perspective_transform(image, corners) if corners is not None else image

        # Lưu ảnh thẻ đã chỉnh
        cv2.imwrite(os.path.join(save_dir, "card_warped.jpg"), card)

        # Lưu từng vùng
        for region_name in CCCD_REGIONS:
            region = crop_region(card, region_name)
            cv2.imwrite(os.path.join(save_dir, f"region_{region_name}.jpg"), region)
            print(f"Saved: {save_dir}/region_{region_name}.jpg")

        print(f"\n📁 Đã lưu debug ảnh vào: {save_dir}/")
        print("👉 Kiểm tra các ảnh để điều chỉnh tọa độ trong CCCD_REGIONS nếu cần.")


# ─────────────────────────────────────────────
# CHẠY THỬ
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    reader = CCCDReader()

    if len(sys.argv) < 2:
        print("Usage: python reader.py <đường_dẫn_ảnh_cccd>")
        print("       python reader.py <ảnh> --calibrate")
        sys.exit(1)

    img_path = sys.argv[1]

    if len(sys.argv) > 2 and sys.argv[2] == "--calibrate":
        # Chế độ debug: lưu từng vùng cắt ra để kiểm tra
        reader.calibrate(img_path)
    else:
        result = reader.read(img_path)
        print(json.dumps(result, ensure_ascii=False, indent=2))
