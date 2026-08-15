"""
Tiền xử lý ảnh nâng cao - Xử lý ảnh mờ, nghiêng, ánh sáng xấu
================================================================
Tất cả đều là thuật toán kinh điển, không dùng AI model.

Các vấn đề thực tế:
  - Ảnh mờ (motion blur, out-of-focus)
  - Ánh sáng không đều (bóng, phản sáng)
  - Nghiêng các hướng (đã xử lý trong reader.py)
  - Ảnh nhiễu (noise)
  - Ảnh tối / quá sáng
"""

import cv2
import numpy as np


# ─────────────────────────────────────────────
# 1. LÀM SẮC NÉT ẢNH MỜ (Sharpening)
# ─────────────────────────────────────────────

def sharpen(image):
    """
    Làm sắc nét ảnh bị mờ bằng Unsharp Masking.

    Công thức:
        sharp = original + alpha * (original - blurred)

    Ý nghĩa:
    - Blur ảnh để lấy phần "mềm" (low-frequency)
    - Trừ khỏi ảnh gốc để lấy phần "nét" (high-frequency = chi tiết)
    - Cộng thêm vào ảnh gốc → tăng chi tiết
    """
    # Gaussian blur để lấy phần mờ
    blurred = cv2.GaussianBlur(image, (0, 0), sigmaX=3)

    # Unsharp Mask: original + 1.5 * (original - blurred)
    # = 2.5 * original - 1.5 * blurred
    sharpened = cv2.addWeighted(image, 2.5, blurred, -1.5, 0)

    return sharpened


def laplacian_sharpen(image):
    """
    Làm sắc nét bằng bộ lọc Laplacian (đạo hàm bậc 2).

    Kernel Laplacian phát hiện cạnh (vùng thay đổi nhanh):
    [0  -1   0]
    [-1  5  -1]
    [0  -1   0]

    Cộng vào ảnh gốc để tăng độ sắc nét.
    """
    kernel = np.array([
        [0,  -1,  0],
        [-1,  5, -1],
        [0,  -1,  0]
    ], dtype=np.float32)

    sharpened = cv2.filter2D(image, -1, kernel)
    return sharpened


# ─────────────────────────────────────────────
# 2. CÂN BẰNG ÁNH SÁNG KHÔNG ĐỀU (CLAHE)
# ─────────────────────────────────────────────

def enhance_contrast(image):
    """
    CLAHE - Contrast Limited Adaptive Histogram Equalization.
    Cân bằng độ sáng tốt hơn Histogram Equalization thường.

    Tại sao dùng CLAHE?
    - Histogram Equalization thường: cân bằng toàn ảnh → vùng tối bị "nhòe"
    - CLAHE: chia ảnh thành nhiều ô nhỏ, cân bằng từng ô
             → Xử lý được ánh sáng không đều (bóng che một góc)
    - "Contrast Limited": giới hạn khuếch đại nhiễu (clipLimit)

    Ứng dụng: Ảnh chụp dưới ánh đèn huỳnh quang, có bóng tay, phản sáng
    """
    if len(image.shape) == 3:
        # Chuyển sang LAB color space
        # L = Lightness (độ sáng), A/B = màu sắc
        # Chỉ cân bằng kênh L, giữ nguyên màu
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)

        # Tạo CLAHE với:
        # clipLimit=3.0: giới hạn khuếch đại (tránh noise)
        # tileGridSize=(8,8): chia ảnh thành 8x8 = 64 ô nhỏ
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l_enhanced = clahe.apply(l)

        # Ghép lại và chuyển về BGR
        enhanced = cv2.merge([l_enhanced, a, b])
        return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
    else:
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        return clahe.apply(image)


# ─────────────────────────────────────────────
# 3. KHỬ NHIỄU (Denoising)
# ─────────────────────────────────────────────

def denoise(image):
    """
    Khử nhiễu bằng Non-Local Means Denoising.

    Nguyên lý: Thay vì trung bình các pixel lân cận (Gaussian blur),
    tìm kiếm toàn bộ ảnh để tìm các vùng tương tự → trung bình có trọng số.
    → Khử nhiễu mà VẪN GIỮ được cạnh sắc nét (không làm mờ viền chữ)

    h=10: Cường độ lọc noise (tăng → khử nhiễu hơn nhưng mất chi tiết)
    """
    if len(image.shape) == 3:
        return cv2.fastNlMeansDenoisingColored(image, None, h=10, hColor=10,
                                               templateWindowSize=7,
                                               searchWindowSize=21)
    else:
        return cv2.fastNlMeansDenoising(image, None, h=10,
                                        templateWindowSize=7,
                                        searchWindowSize=21)


# ─────────────────────────────────────────────
# 4. PHÁT HIỆN VÀ CHỈNH ĐỘ NGHIÊNG NHỎ (Deskew)
# ─────────────────────────────────────────────

def deskew(image):
    """
    Phát hiện và chỉnh góc nghiêng nhỏ (< 45°) bằng Hough Line Transform.

    Ý tưởng:
    1. Canny: tìm các cạnh (đường kẻ trên thẻ)
    2. HoughLines: tìm tất cả đường thẳng trong ảnh
    3. Tính góc trung vị của các đường ngang
    4. Xoay ảnh ngược lại để chỉnh thẳng

    Lưu ý: Chỉ cần dùng khi detect_card() thất bại (không tìm được 4 góc thẻ).
    Trong reader.py, perspective_transform() đã xử lý nghiêng lớn rồi.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    # Hough Line Transform: tìm đường thẳng trong ảnh
    # threshold=100: cần ít nhất 100 điểm ảnh trên đường để công nhận
    lines = cv2.HoughLines(edges, rho=1, theta=np.pi / 180, threshold=100)

    if lines is None:
        return image  # Không tìm được đường → trả về gốc

    # Lấy góc của các đường gần ngang (theta ≈ 90°)
    angles = []
    for line in lines:
        rho, theta = line[0]
        # Chỉ lấy đường gần ngang (80° - 100°)
        if np.pi * 0.44 < theta < np.pi * 0.56:
            angle_deg = np.degrees(theta) - 90
            angles.append(angle_deg)

    if not angles:
        return image

    # Dùng trung vị để tránh outliers
    median_angle = np.median(angles)

    # Bỏ qua nếu góc quá nhỏ (< 0.5°) để tránh distortion không cần thiết
    if abs(median_angle) < 0.5:
        return image

    # Xoay ảnh ngược góc nghiêng phát hiện được
    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    rotated = cv2.warpAffine(image, M, (w, h),
                              flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_REPLICATE)

    return rotated


# ─────────────────────────────────────────────
# 5. PHÁT HIỆN VÀ SỬA MOTION BLUR
# ─────────────────────────────────────────────

def detect_blur_score(image) -> float:
    """
    Đo mức độ mờ của ảnh bằng Laplacian Variance.

    Nguyên lý:
    - Laplacian phát hiện cạnh (vùng thay đổi pixel nhanh)
    - Ảnh sắc nét → nhiều cạnh rõ → variance cao
    - Ảnh mờ → ít cạnh → variance thấp

    Returns:
        score: càng cao càng sắc nét
               < 50: mờ nhiều
               50-100: mờ vừa
               > 100: sắc nét
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    return float(laplacian.var())


def deblur_wiener(image):
    """
    Wiener Filter - Khử motion blur bằng phép khử tích chập (deconvolution).

    Nguyên lý (lý thuyết tín hiệu):
    - Ảnh mờ = ảnh gốc * kernel_blur  (convolution trong miền không gian)
    - Trong miền tần số: F_blur = F_original × H_blur
    - Wiener filter: F_original ≈ F_blur / H_blur  (deconvolution)
    - Có thêm regularization để tránh noise bùng nổ

    Đây là thuật toán toán học thuần túy (signal processing).
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

    # Giả sử motion blur theo chiều ngang, kernel dài 15 pixel
    # Thực tế cần ước lượng kernel từ ảnh (PSF estimation) - phức tạp hơn
    kernel_size = 15
    kernel = np.zeros((kernel_size, kernel_size))
    kernel[kernel_size // 2, :] = 1.0 / kernel_size  # Horizontal blur kernel

    # Chuyển sang miền tần số bằng FFT (Fast Fourier Transform)
    gray_f = np.fft.fft2(gray.astype(np.float64))
    kernel_f = np.fft.fft2(kernel, s=gray.shape)

    # Wiener filter: H* / (|H|^2 + SNR_inverse)
    # SNR_inverse = 1/SNR ≈ 0.01 (noise regularization)
    snr_inv = 0.01
    wiener_f = np.conj(kernel_f) / (np.abs(kernel_f) ** 2 + snr_inv)

    # Áp dụng filter trong miền tần số rồi chuyển về không gian
    restored_f = gray_f * wiener_f
    restored = np.abs(np.fft.ifft2(restored_f))

    # Chuẩn hóa về [0, 255]
    restored = np.clip(restored, 0, 255).astype(np.uint8)

    if len(image.shape) == 3:
        result = image.copy()
        result[:, :, 0] = restored
        result[:, :, 1] = restored
        result[:, :, 2] = restored
        return result
    return restored


# ─────────────────────────────────────────────
# 6. PIPELINE HOÀN CHỈNH
# ─────────────────────────────────────────────

def smart_preprocess(image, debug=False):
    """
    Pipeline tiền xử lý thông minh - tự chọn bước phù hợp.

    Quy trình:
    1. Kiểm tra độ mờ → nếu mờ thì sharpen
    2. Cân bằng ánh sáng (CLAHE) → luôn luôn
    3. Khử nhiễu → nếu cần
    4. Chỉnh nghiêng nhỏ → nếu detect_card thất bại

    Returns:
        processed: ảnh đã xử lý
        report: dict mô tả các bước đã làm
    """
    report = {}

    # Bước 0: Đo chất lượng ảnh ban đầu
    blur_score = detect_blur_score(image)
    report["blur_score_original"] = round(blur_score, 2)
    report["is_blurry"] = blur_score < 80

    processed = image.copy()

    # Bước 1: Cân bằng ánh sáng (luôn làm)
    processed = enhance_contrast(processed)
    report["applied_clahe"] = True

    # Bước 2: Nếu ảnh mờ → sharpen
    if blur_score < 80:
        processed = sharpen(processed)
        new_blur_score = detect_blur_score(processed)
        report["applied_sharpen"] = True
        report["blur_score_after_sharpen"] = round(new_blur_score, 2)

        # Nếu vẫn còn mờ nhiều → thử Laplacian sharpen thêm
        if new_blur_score < 50:
            processed = laplacian_sharpen(processed)
            report["applied_laplacian_sharpen"] = True

    # Bước 3: Khử nhiễu nhẹ
    # Chỉ làm nếu blur_score vừa phải (nếu quá mờ thì denoise sau sharpen)
    if blur_score > 50:
        processed = denoise(processed)
        report["applied_denoise"] = True

    if debug:
        print("Preprocessing report:")
        for k, v in report.items():
            print(f"  {k}: {v}")

    return processed, report


# ─────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python preprocessing.py <image_path>")
        sys.exit(1)

    img = cv2.imread(sys.argv[1])
    if img is None:
        print("Khong doc duoc anh!")
        sys.exit(1)

    print(f"Blur score: {detect_blur_score(img):.2f}")

    processed, report = smart_preprocess(img, debug=True)

    # Luu ket qua
    cv2.imwrite("debug_original.jpg", img)
    cv2.imwrite("debug_processed.jpg", processed)
    print("Da luu: debug_original.jpg va debug_processed.jpg")
