"""
Data Augmentation Pipeline
==========================
Từ 1 ảnh chữ số → tạo ra 50+ biến thể để train CNN.

Kỹ thuật augmentation (tất cả classical, không dùng AI):
  - Xoay nhẹ (±15°)
  - Co/giãn (scale)
  - Dịch chuyển (translation)
  - Thêm nhiễu Gaussian
  - Làm mờ nhẹ
  - Thay đổi độ sáng/tương phản
  - Biến dạng co giãn đàn hồi (elastic distortion)
  - Perspective transform nhẹ
"""

import cv2
import numpy as np
import os
import random
from pathlib import Path


# ─────────────────────────────────────────────
# CÁC HÀM AUGMENTATION
# ─────────────────────────────────────────────

def rotate(img, max_angle=15):
    """Xoay ảnh ngẫu nhiên ±max_angle độ."""
    angle = random.uniform(-max_angle, max_angle)
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(img, M, (w, h), borderValue=255)


def scale(img, min_scale=0.85, max_scale=1.15):
    """Co/giãn ảnh ngẫu nhiên."""
    factor = random.uniform(min_scale, max_scale)
    h, w = img.shape[:2]
    new_h, new_w = int(h * factor), int(w * factor)
    scaled = cv2.resize(img, (new_w, new_h))
    # Crop hoặc pad về kích thước gốc
    result = np.ones((h, w), dtype=np.uint8) * 255
    y_off = max(0, (h - new_h) // 2)
    x_off = max(0, (w - new_w) // 2)
    y_end = min(h, y_off + new_h)
    x_end = min(w, x_off + new_w)
    sy_end = min(new_h, y_end - y_off)
    sx_end = min(new_w, x_end - x_off)
    result[y_off:y_end, x_off:x_end] = scaled[:sy_end, :sx_end]
    return result


def translate(img, max_shift=4):
    """Dịch chuyển ảnh ngẫu nhiên."""
    dx = random.randint(-max_shift, max_shift)
    dy = random.randint(-max_shift, max_shift)
    M = np.float32([[1, 0, dx], [0, 1, dy]])
    h, w = img.shape[:2]
    return cv2.warpAffine(img, M, (w, h), borderValue=255)


def add_gaussian_noise(img, sigma_range=(5, 25)):
    """Thêm nhiễu Gaussian để mô phỏng ảnh chụp hạt."""
    sigma = random.uniform(*sigma_range)
    noise = np.random.normal(0, sigma, img.shape).astype(np.float32)
    noisy = img.astype(np.float32) + noise
    return np.clip(noisy, 0, 255).astype(np.uint8)


def blur(img, max_kernel=3):
    """Làm mờ nhẹ để mô phỏng ảnh chụp hơi mất nét."""
    k = random.choice([1, 3, 3, 5])  # 1 = không blur
    if k == 1:
        return img
    return cv2.GaussianBlur(img, (k, k), 0)


def adjust_brightness(img, factor_range=(0.7, 1.3)):
    """Thay đổi độ sáng ngẫu nhiên."""
    factor = random.uniform(*factor_range)
    adjusted = img.astype(np.float32) * factor
    return np.clip(adjusted, 0, 255).astype(np.uint8)


def elastic_distortion(img, alpha=20, sigma=4):
    """
    Biến dạng đàn hồi (Elastic Distortion).
    
    Ý tưởng: dịch chuyển từng pixel một lượng ngẫu nhiên nhỏ
    → Mô phỏng chữ in hơi méo, không đều
    
    alpha: cường độ biến dạng
    sigma: độ mịn của biến dạng (sigma lớn = biến dạng mượt hơn)
    """
    h, w = img.shape[:2]
    
    # Tạo displacement fields ngẫu nhiên
    dx = cv2.GaussianBlur(
        (np.random.rand(h, w) * 2 - 1).astype(np.float32),
        (0, 0), sigma
    ) * alpha
    dy = cv2.GaussianBlur(
        (np.random.rand(h, w) * 2 - 1).astype(np.float32),
        (0, 0), sigma
    ) * alpha
    
    # Tạo lưới tọa độ mới
    x, y = np.meshgrid(np.arange(w), np.arange(h))
    map_x = (x + dx).astype(np.float32)
    map_y = (y + dy).astype(np.float32)
    
    # Remap ảnh theo lưới mới
    distorted = cv2.remap(img, map_x, map_y, cv2.INTER_LINEAR, borderValue=255)
    return distorted


def perspective_warp(img, max_shift=3):
    """Biến dạng phối cảnh nhẹ để mô phỏng chụp hơi nghiêng."""
    h, w = img.shape[:2]
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    
    # Dịch chuyển các góc một lượng nhỏ ngẫu nhiên
    dst = src + np.random.randint(-max_shift, max_shift, src.shape).astype(np.float32)
    
    M = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(img, M, (w, h), borderValue=255)


def add_jpeg_artifact(img, quality_range=(60, 95)):
    """Mô phỏng ảnh bị nén JPEG nhiều lần (artifact)."""
    quality = random.randint(*quality_range)
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    _, encoded = cv2.imencode('.jpg', img, encode_param)
    decoded = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)
    return decoded


# ─────────────────────────────────────────────
# AUGMENT 1 ẢNH → N BIẾN THỂ
# ─────────────────────────────────────────────

ALL_AUGMENTATIONS = [
    rotate,
    scale,
    translate,
    add_gaussian_noise,
    blur,
    adjust_brightness,
    elastic_distortion,
    perspective_warp,
    add_jpeg_artifact,
]


def augment_one(img, target_size=(32, 32)):
    """
    Áp dụng ngẫu nhiên 2-4 phép augmentation lên 1 ảnh.
    Trả về ảnh đã augment, resize về target_size.
    """
    result = img.copy()
    
    # Chọn ngẫu nhiên 2-4 phép augmentation
    n_augs = random.randint(2, 4)
    chosen = random.sample(ALL_AUGMENTATIONS, n_augs)
    
    for aug_fn in chosen:
        try:
            result = aug_fn(result)
        except Exception:
            pass  # Bỏ qua nếu lỗi (ảnh quá nhỏ, etc.)
    
    # Resize về kích thước chuẩn
    result = cv2.resize(result, target_size)
    return result


def augment_dataset(input_dir: str, output_dir: str, n_per_image: int = 50):
    """
    Augment toàn bộ dataset.
    
    Cấu trúc input_dir:
        input_dir/
            0/  ← chứa ảnh chữ số 0
                img001.png
                img002.png
                ...
            1/  ← chứa ảnh chữ số 1
            ...
            9/
    
    Cấu trúc output_dir (tương tự):
        output_dir/
            0/  ← chứa ảnh augmented của chữ số 0
            1/
            ...
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    total_generated = 0
    
    for digit in range(10):
        digit_dir = input_path / str(digit)
        out_dir = output_path / str(digit)
        out_dir.mkdir(parents=True, exist_ok=True)
        
        if not digit_dir.exists():
            print(f"  [SKIP] Khong co thu muc: {digit_dir}")
            continue
        
        images = list(digit_dir.glob("*.png")) + list(digit_dir.glob("*.jpg"))
        if not images:
            print(f"  [SKIP] Khong co anh trong: {digit_dir}")
            continue
        
        print(f"  Digit '{digit}': {len(images)} anh goc -> tao {len(images) * n_per_image} anh...")
        
        count = 0
        for img_path in images:
            img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue
            
            # Lưu ảnh gốc
            cv2.imwrite(str(out_dir / f"orig_{img_path.stem}.png"), 
                       cv2.resize(img, (32, 32)))
            count += 1
            
            # Tạo n_per_image biến thể
            for i in range(n_per_image):
                aug_img = augment_one(img)
                save_path = out_dir / f"aug_{img_path.stem}_{i:04d}.png"
                cv2.imwrite(str(save_path), aug_img)
                count += 1
        
        print(f"    -> Da tao {count} anh cho digit '{digit}'")
        total_generated += count
    
    print(f"\nTong cong: {total_generated} anh da duoc tao tai: {output_dir}")
    return total_generated


# ─────────────────────────────────────────────
# CHẠY THỬ
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) >= 3:
        augment_dataset(sys.argv[1], sys.argv[2], n_per_image=50)
    else:
        print("Usage: python augmentation.py <input_dir> <output_dir>")
        print("")
        print("Cau truc input_dir:")
        print("  input_dir/")
        print("    0/  <- anh chu so 0")
        print("    1/  <- anh chu so 1")
        print("    ...")
        print("    9/  <- anh chu so 9")
