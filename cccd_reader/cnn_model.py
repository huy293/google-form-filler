"""
CNN (Convolutional Neural Network) - Tự build và train từ đầu
==============================================================
Nhận dạng chữ số 0-9 từ ảnh CCCD/Hộ chiếu

Kiến trúc LeNet-style (1998, Yann LeCun):
  Input 32x32 → Conv → Pool → Conv → Pool → FC → FC → Output 10 class

Dùng PyTorch chỉ như framework tính toán (như numpy nâng cao).
KHÔNG dùng pre-trained weights. Train từ đầu hoàn toàn.
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import cv2
import numpy as np
import os
import json
from pathlib import Path


# ─────────────────────────────────────────────
# 1. KIẾN TRÚC CNN
# ─────────────────────────────────────────────

class DigitCNN(nn.Module):
    """
    CNN nhỏ nhận dạng chữ số 0-9.

    Kiến trúc:
        INPUT: (batch, 1, 32, 32)  ← ảnh xám 32x32

        Conv1: 1 → 32 filters, kernel 3x3, ReLU
        MaxPool: 2x2 → (batch, 32, 15, 15)

        Conv2: 32 → 64 filters, kernel 3x3, ReLU
        MaxPool: 2x2 → (batch, 64, 6, 6)

        Conv3: 64 → 128 filters, kernel 3x3, ReLU
        → (batch, 128, 4, 4)

        Flatten: → (batch, 2048)
        FC1: 2048 → 256, ReLU, Dropout 0.5
        FC2: 256 → 10, Softmax

    Tại sao dùng Convolution?
    - Chia sẻ trọng số: cùng 1 filter quét toàn ảnh
      → Nhận ra chữ số dù ở vị trí nào trong ảnh
    - Học đặc trưng cục bộ: cạnh, góc, đường cong
    """

    def __init__(self):
        super().__init__()

        # Khối Convolutional 1
        self.conv1 = nn.Sequential(
            nn.Conv2d(in_channels=1, out_channels=32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),     # Chuẩn hóa batch → train nhanh hơn
            nn.ReLU(),              # Hàm kích hoạt: f(x) = max(0, x)
            nn.MaxPool2d(2, 2)      # Giảm chiều 2x: 32x32 → 16x16
        )

        # Khối Convolutional 2
        self.conv2 = nn.Sequential(
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool2d(2, 2)      # 16x16 → 8x8
        )

        # Khối Convolutional 3
        self.conv3 = nn.Sequential(
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(),
            nn.MaxPool2d(2, 2)      # 8x8 → 4x4
        )

        # Lớp Fully Connected
        self.classifier = nn.Sequential(
            nn.Flatten(),                       # (batch, 128, 4, 4) → (batch, 2048)
            nn.Linear(128 * 4 * 4, 256),
            nn.ReLU(),
            nn.Dropout(0.5),                    # Bỏ ngẫu nhiên 50% neuron khi train
            nn.Linear(256, 10)                  # 10 class: 0-9
        )

    def forward(self, x):
        x = self.conv1(x)
        x = self.conv2(x)
        x = self.conv3(x)
        x = self.classifier(x)
        return x                                # Trả về logits (chưa softmax)


# ─────────────────────────────────────────────
# 2. DATASET
# ─────────────────────────────────────────────

class DigitDataset(Dataset):
    """
    Dataset loader cho thư mục:
        data/
          0/ ← ảnh chữ số 0
          1/ ← ảnh chữ số 1
          ...
          9/
    """

    def __init__(self, root_dir: str, augment: bool = False):
        self.samples = []   # List of (image_path, label)
        self.augment = augment

        root = Path(root_dir)
        for digit in range(10):
            digit_dir = root / str(digit)
            if not digit_dir.exists():
                continue
            for img_path in digit_dir.glob("*.png"):
                self.samples.append((str(img_path), digit))
            for img_path in digit_dir.glob("*.jpg"):
                self.samples.append((str(img_path), digit))

        print(f"Dataset loaded: {len(self.samples)} samples")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        img_path, label = self.samples[idx]

        # Đọc ảnh xám
        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            img = np.zeros((32, 32), dtype=np.uint8)

        # Resize về 32x32
        img = cv2.resize(img, (32, 32))

        # Chuẩn hóa về [0, 1]
        img = img.astype(np.float32) / 255.0

        # Thêm chiều channel: (32, 32) → (1, 32, 32)
        img = np.expand_dims(img, axis=0)

        return torch.tensor(img), torch.tensor(label, dtype=torch.long)


# ─────────────────────────────────────────────
# 3. TRAINING
# ─────────────────────────────────────────────

def train(data_dir: str, model_save_path: str = "digit_cnn.pth",
          epochs: int = 30, batch_size: int = 64, lr: float = 0.001):
    """
    Train CNN từ đầu.

    Args:
        data_dir: Thư mục chứa data (có cấu trúc 0/, 1/, ..., 9/)
        model_save_path: Nơi lưu model sau khi train
        epochs: Số lần duyệt toàn bộ dataset
        batch_size: Số ảnh mỗi lần cập nhật trọng số
        lr: Learning rate - tốc độ học
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on: {device}")

    # Load data
    dataset = DigitDataset(data_dir)
    n_total = len(dataset)
    n_train = int(n_total * 0.85)  # 85% train
    n_val = n_total - n_train       # 15% validation

    train_set, val_set = torch.utils.data.random_split(dataset, [n_train, n_val])

    train_loader = DataLoader(train_set, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_set, batch_size=batch_size)

    print(f"Train: {n_train} | Val: {n_val}")

    # Khởi tạo model
    model = DigitCNN().to(device)
    print(f"Parameters: {sum(p.numel() for p in model.parameters()):,}")

    # Loss function: Cross Entropy (phù hợp bài toán classification)
    # CE = -sum(y_true * log(y_pred))
    criterion = nn.CrossEntropyLoss()

    # Optimizer: Adam (adaptive learning rate)
    # Tốt hơn SGD thường: tự điều chỉnh lr cho từng parameter
    optimizer = optim.Adam(model.parameters(), lr=lr)

    # Learning rate scheduler: giảm lr khi val_loss không cải thiện
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=3, factor=0.5)

    # Training loop
    best_val_acc = 0.0
    history = {"train_loss": [], "train_acc": [], "val_loss": [], "val_acc": []}

    for epoch in range(1, epochs + 1):
        # ── TRAIN ──
        model.train()
        train_loss, train_correct = 0.0, 0

        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)

            optimizer.zero_grad()           # Reset gradient
            outputs = model(images)         # Forward pass
            loss = criterion(outputs, labels)  # Tính loss
            loss.backward()                 # Backpropagation
            optimizer.step()                # Cập nhật trọng số

            train_loss += loss.item() * len(images)
            train_correct += (outputs.argmax(1) == labels).sum().item()

        train_loss /= n_train
        train_acc = train_correct / n_train

        # ── VALIDATION ──
        model.eval()
        val_loss, val_correct = 0.0, 0

        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                outputs = model(images)
                loss = criterion(outputs, labels)
                val_loss += loss.item() * len(images)
                val_correct += (outputs.argmax(1) == labels).sum().item()

        val_loss /= n_val
        val_acc = val_correct / n_val

        scheduler.step(val_loss)

        # Lưu model tốt nhất
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), model_save_path)
            saved = " <- SAVED"
        else:
            saved = ""

        history["train_loss"].append(train_loss)
        history["train_acc"].append(train_acc)
        history["val_loss"].append(val_loss)
        history["val_acc"].append(val_acc)

        print(f"Epoch {epoch:3d}/{epochs} | "
              f"Train Loss: {train_loss:.4f} Acc: {train_acc:.1%} | "
              f"Val Loss: {val_loss:.4f} Acc: {val_acc:.1%}{saved}")

    print(f"\nBest Val Accuracy: {best_val_acc:.1%}")
    print(f"Model saved: {model_save_path}")

    # Lưu history
    with open("training_history.json", "w") as f:
        json.dump(history, f)

    return best_val_acc


# ─────────────────────────────────────────────
# 4. INFERENCE (Dùng model đã train)
# ─────────────────────────────────────────────

class CNNDigitRecognizer:
    """
    Dùng model đã train để nhận dạng chữ số.
    Thay thế cho TemplateMatchingOCR trong reader.py.
    """

    def __init__(self, model_path: str):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = DigitCNN().to(self.device)

        if os.path.exists(model_path):
            self.model.load_state_dict(
                torch.load(model_path, map_location=self.device)
            )
            self.model.eval()
            print(f"Model loaded: {model_path}")
        else:
            print(f"WARNING: Model not found at {model_path}")

    def recognize_digit(self, char_img_gray) -> tuple[str, float]:
        """Nhận dạng 1 ký tự, trả về (char, confidence)."""
        img = cv2.resize(char_img_gray, (32, 32)).astype(np.float32) / 255.0
        img_tensor = torch.tensor(img).unsqueeze(0).unsqueeze(0).to(self.device)

        with torch.no_grad():
            logits = self.model(img_tensor)
            probs = torch.softmax(logits, dim=1)
            confidence, predicted = probs.max(1)

        return str(predicted.item()), float(confidence.item())

    def recognize_line(self, region_img) -> str:
        """Nhận dạng 1 dòng số từ ảnh vùng (tương tự TemplateMatchingOCR)."""
        if len(region_img.shape) == 3:
            gray = cv2.cvtColor(region_img, cv2.COLOR_BGR2GRAY)
        else:
            gray = region_img

        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        h_img = thresh.shape[0]
        valid_chars = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if h > h_img * 0.3 and w > 3:
                char_img = thresh[y:y + h, x:x + w]
                valid_chars.append((x, char_img))

        valid_chars.sort(key=lambda c: c[0])

        result = ""
        for _, char_img in valid_chars:
            ch, conf = self.recognize_digit(char_img)
            result += ch if conf > 0.5 else "?"

        return result


# ─────────────────────────────────────────────
# CHẠY TRAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  Train:   python cnn_model.py train <data_dir>")
        print("  Test:    python cnn_model.py test <model.pth> <image.png> <label>")
        sys.exit(1)

    if sys.argv[1] == "train":
        data_dir = sys.argv[2] if len(sys.argv) > 2 else "data_augmented"
        train(data_dir, model_save_path="digit_cnn.pth", epochs=30)

    elif sys.argv[1] == "test":
        model_path = sys.argv[2]
        img_path = sys.argv[3]
        true_label = sys.argv[4] if len(sys.argv) > 4 else "?"

        recognizer = CNNDigitRecognizer(model_path)
        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        pred, conf = recognizer.recognize_digit(img)
        print(f"Predicted: {pred} (confidence: {conf:.1%}) | True: {true_label}")
