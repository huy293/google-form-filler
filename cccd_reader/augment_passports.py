"""
Augment 24 real passport images -> ~500 varied training images
Techniques: rotate, flip, brightness, contrast, noise, crop, blur, perspective
"""
import cv2, numpy as np, os, random
from pathlib import Path

SRC  = Path(r'C:\Users\luuhu\Downloads\Passprot')
OUT  = Path('passport_augmented')
OUT.mkdir(exist_ok=True)

def random_rotate(img, max_angle=20):
    h, w = img.shape[:2]
    angle = random.uniform(-max_angle, max_angle)
    M = cv2.getRotationMatrix2D((w//2, h//2), angle, 1.0)
    return cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REFLECT)

def random_brightness(img):
    factor = random.uniform(0.5, 1.5)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:,:,2] = np.clip(hsv[:,:,2] * factor, 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

def random_noise(img):
    noise = np.random.randn(*img.shape).astype(np.float32) * random.uniform(5, 25)
    return np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)

def random_blur(img):
    k = random.choice([3, 5, 7])
    return cv2.GaussianBlur(img, (k, k), 0)

def random_contrast(img):
    alpha = random.uniform(0.7, 1.5)  # contrast
    beta  = random.uniform(-30, 30)   # brightness
    return np.clip(img.astype(np.float32)*alpha + beta, 0, 255).astype(np.uint8)

def random_perspective(img):
    h, w = img.shape[:2]
    margin = int(min(h, w) * 0.08)
    pts1 = np.float32([[0,0],[w,0],[0,h],[w,h]])
    pts2 = np.float32([
        [random.randint(0, margin), random.randint(0, margin)],
        [w - random.randint(0, margin), random.randint(0, margin)],
        [random.randint(0, margin), h - random.randint(0, margin)],
        [w - random.randint(0, margin), h - random.randint(0, margin)],
    ])
    M = cv2.getPerspectiveTransform(pts1, pts2)
    return cv2.warpPerspective(img, M, (w, h), borderMode=cv2.BORDER_REFLECT)

def random_crop_resize(img):
    h, w = img.shape[:2]
    crop_pct = random.uniform(0.7, 0.95)
    new_h, new_w = int(h*crop_pct), int(w*crop_pct)
    y = random.randint(0, h - new_h)
    x = random.randint(0, w - new_w)
    cropped = img[y:y+new_h, x:x+new_w]
    return cv2.resize(cropped, (w, h))

def random_jpeg_quality(img):
    q = random.randint(55, 95)
    _, enc = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, q])
    return cv2.imdecode(enc, cv2.IMREAD_COLOR)

AUGMENTATIONS = [
    ('rot',   random_rotate),
    ('bright',random_brightness),
    ('noise', random_noise),
    ('blur',  random_blur),
    ('cont',  random_contrast),
    ('persp', random_perspective),
    ('crop',  random_crop_resize),
    ('jpeg',  random_jpeg_quality),
]

# Combination augments (2 transforms at once)
def augment_combo(img):
    fns = random.sample([f for _, f in AUGMENTATIONS], k=random.randint(2, 3))
    for fn in fns:
        img = fn(img)
    return img

imgs = sorted(SRC.glob('*.jpg'))
print(f'Source images: {len(imgs)}')

total = 0
N_PER_IMAGE = 20  # 24 x 20 = 480 augmented images

for img_path in imgs:
    img = cv2.imread(str(img_path))
    if img is None: continue
    
    # Resize to standard size (max 1200px wide) to save space
    h, w = img.shape[:2]
    if w > 1200:
        scale = 1200/w
        img = cv2.resize(img, (1200, int(h*scale)))
    
    stem = img_path.stem[:20]
    
    # Save original (resize only)
    cv2.imwrite(str(OUT / f'{stem}_orig.jpg'), img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    total += 1
    
    # N augmented versions
    for i in range(N_PER_IMAGE):
        aug = augment_combo(img.copy())
        fname = OUT / f'{stem}_aug{i+1:03d}.jpg'
        cv2.imwrite(str(fname), aug, [cv2.IMWRITE_JPEG_QUALITY, 85])
        total += 1
    
    print(f'  {stem}: +{N_PER_IMAGE+1} (total={total})')

print(f'\n=== DONE: {total} images -> {OUT}/ ===')
