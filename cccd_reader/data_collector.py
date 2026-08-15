"""
Thu thập ảnh giấy tờ từ nhiều nguồn công khai
==============================================
Nguồn 1: PRADO (Hội đồng Châu Âu) - dùng Playwright browser thật
Nguồn 2: MIDV dataset (dataset học thuật mở)
Nguồn 3: Sinh ảnh số tổng hợp (synthetic - không cần internet)

Mục tiêu: 5000+ ảnh chữ số đã gán nhãn để train CNN
"""

import asyncio
import os
import json
import cv2
import numpy as np
import urllib.request
from pathlib import Path


# ─────────────────────────────────────────────────────────────────
# NGUỒN 1: PRADO - Playwright scraper
# ─────────────────────────────────────────────────────────────────

# Danh sách mã quốc gia PRADO + loại tài liệu
# Format: (country_code, doc_type, versions)
# BO = Hộ chiếu, BI = ID card
PRADO_DOCS = [
    # Hộ chiếu
    ("VNM", "BO", range(1, 5)),   # Việt Nam
    ("DEU", "BO", range(1, 8)),   # Đức
    ("FRA", "BO", range(1, 8)),   # Pháp
    ("GBR", "BO", range(1, 6)),   # Anh
    ("USA", "BO", range(1, 5)),   # Mỹ
    ("KOR", "BO", range(1, 5)),   # Hàn Quốc
    ("JPN", "BO", range(1, 5)),   # Nhật Bản
    ("LTU", "BO", range(1, 4)),   # Lithuania
    ("AUS", "BO", range(1, 4)),   # Úc
    ("CAN", "BO", range(1, 4)),   # Canada
    ("CHN", "BO", range(1, 4)),   # Trung Quốc
    ("TWN", "BO", range(1, 3)),   # Đài Loan
    ("RUS", "BO", range(1, 5)),   # Nga
    ("IND", "BO", range(1, 4)),   # Ấn Độ
    ("SGP", "BO", range(1, 4)),   # Singapore
    # CCCD / ID card
    ("VNM", "BI", range(1, 4)),   # CCCD Việt Nam
    ("DEU", "BI", range(1, 6)),   # ID Đức
    ("FRA", "BI", range(1, 4)),   # ID Pháp
    ("KOR", "BI", range(1, 3)),   # ID Hàn Quốc
    ("LTU", "BI", range(1, 4)),   # ID Lithuania
]


async def scrape_prado(output_dir: str = "raw_images/prado"):
    """
    Dùng Playwright (browser thật) scrape ảnh từ PRADO.
    PRADO chặn urllib/requests nhưng không chặn browser thật.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("Can't find playwright. Install: pip install playwright && playwright install chromium")
        return 0

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    total = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"
        )
        page = await context.new_page()

        for country, doc_type, versions in PRADO_DOCS:
            for ver in versions:
                doc_id = f"{country}-{doc_type}-{ver:05d}"
                url = f"https://www.consilium.europa.eu/prado/en/{doc_id}/index.html"

                try:
                    resp = await page.goto(url, timeout=15000, wait_until="domcontentloaded")
                    if resp and resp.status == 200:
                        # Tìm tất cả ảnh trong trang
                        imgs = await page.query_selector_all("img")
                        for i, img in enumerate(imgs):
                            src = await img.get_attribute("src")
                            if src and any(ext in src.lower() for ext in [".jpg", ".jpeg", ".png"]):
                                # Download ảnh
                                if src.startswith("/"):
                                    src = "https://www.consilium.europa.eu" + src
                                
                                save_name = f"{country}_{doc_type}_{ver:02d}_{i:02d}.jpg"
                                save_path = os.path.join(output_dir, save_name)
                                
                                try:
                                    await page.evaluate(f"""
                                        fetch('{src}').then(r=>r.blob()).then(b=>{{
                                            const a=document.createElement('a');
                                            a.href=URL.createObjectURL(b);
                                            a.download='{save_name}';
                                        }});
                                    """)
                                    # Dùng playwright download
                                    img_data = await page.evaluate(f"""
                                        async () => {{
                                            const r = await fetch('{src}');
                                            const b = await r.arrayBuffer();
                                            return Array.from(new Uint8Array(b));
                                        }}
                                    """)
                                    with open(save_path, "wb") as f:
                                        f.write(bytes(img_data))
                                    total += 1
                                    print(f"  Downloaded: {save_name}")
                                except Exception as e:
                                    pass

                        await asyncio.sleep(1)  # Tránh bị ban

                except Exception as e:
                    pass  # Tài liệu không tồn tại → bỏ qua

        await browser.close()

    print(f"\nPRADO: Downloaded {total} images to {output_dir}")
    return total


# ─────────────────────────────────────────────────────────────────
# NGUỒN 2: SYNTHETIC DATA - Tự tạo ảnh số (không cần internet)
# ─────────────────────────────────────────────────────────────────

FONTS = [
    cv2.FONT_HERSHEY_SIMPLEX,
    cv2.FONT_HERSHEY_PLAIN,
    cv2.FONT_HERSHEY_DUPLEX,
    cv2.FONT_HERSHEY_COMPLEX,
    cv2.FONT_HERSHEY_TRIPLEX,
    cv2.FONT_HERSHEY_COMPLEX_SMALL,
    cv2.FONT_HERSHEY_SCRIPT_SIMPLEX,
]

try:
    from PIL import ImageFont, ImageDraw, Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def generate_synthetic_digit(digit: int, size: int = 32) -> np.ndarray:
    """
    Sinh 1 ảnh chữ số với biến thể ngẫu nhiên:
    - Font ngẫu nhiên
    - Kích thước ngẫu nhiên
    - Màu nền/chữ hơi biến đổi (mô phỏng in ấn)
    - Nhiễu nhẹ
    """
    import random

    # Ảnh nền trắng hơi biến đổi
    bg = random.randint(230, 255)
    img = np.ones((size, size), dtype=np.uint8) * bg

    # Màu chữ đen hơi biến đổi
    fg = random.randint(0, 30)

    # Chọn font ngẫu nhiên
    font = random.choice(FONTS)
    font_scale = random.uniform(0.7, 1.1)
    thickness = random.choice([1, 2, 2, 3])

    text = str(digit)
    (tw, th), baseline = cv2.getTextSize(text, font, font_scale, thickness)

    # Vị trí hơi lệch ngẫu nhiên
    x = (size - tw) // 2 + random.randint(-3, 3)
    y = (size + th) // 2 + random.randint(-3, 3)
    x = max(0, min(size - tw, x))
    y = max(th, min(size, y))

    cv2.putText(img, text, (x, y), font, font_scale, fg, thickness, cv2.LINE_AA)

    # Thêm nhiễu Gaussian nhẹ
    noise = np.random.normal(0, random.uniform(2, 8), img.shape).astype(np.float32)
    img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    return img


def generate_synthetic_dataset(output_dir: str = "raw_data", n_per_digit: int = 100):
    """
    Tạo n_per_digit ảnh tổng hợp cho mỗi chữ số 0-9.
    Tổng: 10 × n_per_digit ảnh.
    Không cần internet, không cần dữ liệu thật.
    """
    import random
    print(f"\nSinh du lieu tong hop: {n_per_digit} anh/so...")

    total = 0
    for digit in range(10):
        digit_dir = Path(output_dir) / str(digit)
        digit_dir.mkdir(parents=True, exist_ok=True)

        for i in range(n_per_digit):
            img = generate_synthetic_digit(digit)
            save_path = digit_dir / f"synthetic_{i:04d}.png"
            cv2.imwrite(str(save_path), img)
            total += 1

        print(f"  Digit '{digit}': {n_per_digit} anh")

    print(f"Tong: {total} anh synthetic tai {output_dir}/")
    return total


# ─────────────────────────────────────────────────────────────────
# NGUỒN 3: MNIST - Dataset chữ số viết tay (70.000 ảnh)
# ─────────────────────────────────────────────────────────────────

def download_mnist(output_dir: str = "raw_data", n_per_digit: int = 200):
    """
    Download MNIST dataset (chữ số viết tay, 70.000 ảnh).
    Dùng để tăng tính tổng quát của model.

    MNIST: http://yann.lecun.com/exdb/mnist/
    Torchvision cung cấp API download tiện lợi.
    """
    print(f"\nDownloading MNIST ({n_per_digit} anh/so)...")

    try:
        import torchvision
        import torchvision.transforms as transforms

        transform = transforms.Compose([
            transforms.Resize((32, 32)),
            transforms.ToTensor(),
        ])

        # Download MNIST tự động
        mnist = torchvision.datasets.MNIST(
            root="./mnist_data", train=True, download=True, transform=transform
        )

        # Lưu n_per_digit ảnh mỗi chữ số
        counts = {d: 0 for d in range(10)}
        total = 0

        for img_tensor, label in mnist:
            digit = int(label)
            if counts[digit] >= n_per_digit:
                continue

            digit_dir = Path(output_dir) / str(digit)
            digit_dir.mkdir(parents=True, exist_ok=True)

            # Convert tensor → numpy → lưu ảnh
            img_np = (img_tensor.squeeze().numpy() * 255).astype(np.uint8)
            # MNIST là chữ đen trên nền trắng → đảo lại như CCCD
            img_np = 255 - img_np

            save_path = digit_dir / f"mnist_{counts[digit]:04d}.png"
            cv2.imwrite(str(save_path), img_np)

            counts[digit] += 1
            total += 1

            if all(c >= n_per_digit for c in counts.values()):
                break

        print(f"MNIST: Da luu {total} anh vao {output_dir}/")
        return total

    except ImportError:
        print("Can't find torchvision. Install: pip install torchvision")
        return 0


# ─────────────────────────────────────────────────────────────────
# PIPELINE TỔNG HỢP
# ─────────────────────────────────────────────────────────────────

async def collect_all(target: int = 5000):
    """
    Thu thập từ tất cả nguồn để đạt target ảnh.
    
    Chiến lược:
    - Synthetic: 100 ảnh/digit × 10 = 1.000 ảnh  (không cần internet)
    - MNIST:     200 ảnh/digit × 10 = 2.000 ảnh  (download tự động)
    - PRADO:     ~200 tài liệu × ~10 số = ~2.000  (cần browser)
    - Augment ×5 sau đó = 5.000+ ảnh đã augment
    """
    print("=" * 50)
    print(f"Muc tieu: {target} anh training data")
    print("=" * 50)

    raw_dir = "raw_data"
    total = 0

    # Nguồn 1: Synthetic (không cần internet - làm trước)
    n1 = generate_synthetic_dataset(raw_dir, n_per_digit=100)
    total += n1

    # Nguồn 2: MNIST
    n2 = download_mnist(raw_dir, n_per_digit=200)
    total += n2

    # Nguồn 3: PRADO (nếu cần thêm)
    if total < target // 5:  # Nếu raw data còn ít
        print("\nThu thap anh tu PRADO...")
        n3 = await scrape_prado("raw_images/prado")
        total += n3

    print(f"\nTong raw data: {total} anh")
    print(f"Sau augmentation x10: ~{total * 10} anh")
    print(f"\nBuoc tiep theo:")
    print(f"  python augmentation.py {raw_dir} data_augmented --n 10")
    print(f"  python cnn_model.py train data_augmented")


# ─────────────────────────────────────────────────────────────────
# CHẠY
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "synthetic":
            n = int(sys.argv[2]) if len(sys.argv) > 2 else 100
            generate_synthetic_dataset("raw_data", n_per_digit=n)
        elif cmd == "mnist":
            n = int(sys.argv[2]) if len(sys.argv) > 2 else 200
            download_mnist("raw_data", n_per_digit=n)
        elif cmd == "prado":
            asyncio.run(scrape_prado())
        elif cmd == "all":
            asyncio.run(collect_all())
    else:
        print("Usage:")
        print("  python data_collector.py synthetic [n_per_digit]  <- Sinh anh tong hop (NHANH NHAT)")
        print("  python data_collector.py mnist [n_per_digit]      <- Download MNIST (70k anh)")
        print("  python data_collector.py prado                    <- Scrape PRADO (can browser)")
        print("  python data_collector.py all                      <- Chay tat ca")
