# Công cụ cắt chữ số từ ảnh CCCD để tạo training data
# Chạy: python crop_digits.py <anh_cccd.jpg> <ten_anh>
# Kết quả lưu vào: raw_data/<label>/

"""
Công cụ thu thập dữ liệu:
Crop từng chữ số từ vùng số CCCD → lưu vào thư mục theo nhãn.

Cách dùng:
1. Download ảnh CCCD mẫu từ internet
2. Chạy: python collect_data.py <anh.jpg> <ten>
3. Script sẽ detect thẻ, crop vùng số, tách từng chữ số
4. Bạn xem và gán nhãn thủ công (hoặc tự động nếu ảnh rõ)
"""

import cv2
import numpy as np
import os
import sys
from pathlib import Path

# Import từ reader.py
sys.path.insert(0, os.path.dirname(__file__))
from reader import detect_card, perspective_transform, crop_region, preprocess


def extract_digits_from_cccd(image_path: str, img_name: str, output_dir: str = "raw_data"):
    """
    Từ 1 ảnh CCCD → tách từng chữ số → lưu vào raw_data/unlabeled/
    Sau đó bạn sắp xếp thủ công vào raw_data/0/, raw_data/1/, ...
    """
    unlabeled_dir = Path(output_dir) / "unlabeled" / img_name
    unlabeled_dir.mkdir(parents=True, exist_ok=True)

    img = cv2.imread(image_path)
    if img is None:
        print(f"Khong doc duoc: {image_path}")
        return

    # Detect và chỉnh thẻ
    corners = detect_card(img)
    if corners is not None:
        card = perspective_transform(img, corners)
    else:
        card = img
        print("  Khong tim thay vien the, dung anh goc")

    # Lưu ảnh thẻ đã chỉnh để kiểm tra
    cv2.imwrite(str(unlabeled_dir / "_card.jpg"), card)

    # Crop vùng số CCCD
    number_region = crop_region(card, "cccd_number")
    cv2.imwrite(str(unlabeled_dir / "_region_number.jpg"), number_region)

    # Tách từng chữ số
    gray = cv2.cvtColor(number_region, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    h_img = thresh.shape[0]
    valid = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if h > h_img * 0.3 and w > 3:
            valid.append((x, y, w, h))

    valid.sort(key=lambda c: c[0])  # Sắp xếp trái → phải

    count = 0
    for i, (x, y, w, h) in enumerate(valid):
        # Thêm padding quanh chữ số
        pad = 4
        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(number_region.shape[1], x + w + pad)
        y2 = min(number_region.shape[0], y + h + pad)

        digit_img = cv2.cvtColor(number_region, cv2.COLOR_BGR2GRAY)[y1:y2, x1:x2]
        digit_img = cv2.resize(digit_img, (32, 32))

        save_path = unlabeled_dir / f"digit_{i:02d}.png"
        cv2.imwrite(str(save_path), digit_img)
        count += 1

    print(f"  Da tach {count} chu so tu {image_path}")
    print(f"  Luu tai: {unlabeled_dir}/")
    print(f"  -> Gan nhan thu cong roi chuyen vao raw_data/0/, raw_data/1/, ...")
    return count


def show_labeling_guide():
    print("""
=== HUONG DAN THU THAP DU LIEU ===

Buoc 1: Download anh CCCD mau tu internet
  - Tim tren Google: "can cuoc cong dan mau", "CCCD sample"
  - Lay anh ro, thang, du anh sang
  - Luu vao thu muc: images/

Buoc 2: Chay script nay cho tung anh
  python collect_data.py images/cccd_001.jpg cccd_001

Buoc 3: Kiem tra thu muc raw_data/unlabeled/cccd_001/
  - Xem _region_number.jpg (vung so CCCD)
  - Xem cac digit_XX.png (tung chu so)

Buoc 4: Gan nhan (phan loai thu cong)
  - Tao cac thu muc: raw_data/0/, raw_data/1/, ..., raw_data/9/
  - Di chuyen tung chu so vao dung thu muc
  - Vi du: digit_02.png la so "5" → copy vao raw_data/5/

Buoc 5: Augmentation
  python augmentation.py raw_data data_augmented

Buoc 6: Train CNN
  python cnn_model.py train data_augmented
""")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        show_labeling_guide()
        sys.exit(0)

    if sys.argv[1] == "help":
        show_labeling_guide()
    elif len(sys.argv) >= 3:
        extract_digits_from_cccd(sys.argv[1], sys.argv[2])
    else:
        print("Usage: python collect_data.py <anh_cccd.jpg> <ten_anh>")
