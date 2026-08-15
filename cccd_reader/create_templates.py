"""
Tạo ảnh mẫu chữ số (templates) cho Template Matching OCR.

Tại sao cần file này?
- Template Matching so sánh ký tự cần nhận dạng với ảnh mẫu có sẵn
- File này tạo ra 10 ảnh mẫu: 0.png, 1.png ... 9.png
- Dùng font của OpenCV để vẽ chữ số lên ảnh trắng

Trong thực tế:
- Nên dùng ảnh cắt ra từ CCCD thật (chính xác hơn)
- Chạy file này 1 lần duy nhất để tạo templates
"""

import cv2
import numpy as np
import os


def create_digit_templates(output_dir: str = "templates"):
    """
    Tạo 10 ảnh mẫu chữ số (0-9) bằng cách vẽ bằng OpenCV.

    Lưu ý: Đây là templates cơ bản, dùng font mặc định của OpenCV.
    Để chính xác hơn → cắt chữ số từ ảnh CCCD thật
    và lưu đè lên các file này.
    """
    os.makedirs(output_dir, exist_ok=True)

    for digit in range(10):
        # Tạo ảnh trắng 64x80 pixel
        img = np.ones((80, 64), dtype=np.uint8) * 255

        # Vẽ chữ số màu đen lên giữa ảnh
        text = str(digit)
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 2.0
        thickness = 3

        # Tính vị trí căn giữa
        (text_w, text_h), baseline = cv2.getTextSize(text, font, font_scale, thickness)
        x = (64 - text_w) // 2
        y = (80 + text_h) // 2

        cv2.putText(img, text, (x, y), font, font_scale, 0, thickness, cv2.LINE_AA)

        # Lưu file
        save_path = os.path.join(output_dir, f"{digit}.png")
        cv2.imwrite(save_path, img)
        print(f"  Created: {save_path}")

    print(f"\n✅ Tạo xong {10} templates tại: {output_dir}/")
    print("\n💡 Tips để tăng độ chính xác:")
    print("   1. Chụp ảnh CCCD thật, cắt từng chữ số")
    print("   2. Lưu đè lên templates/0.png ... templates/9.png")
    print("   3. Chạy lại reader.py để test")


if __name__ == "__main__":
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    create_digit_templates(template_dir)
