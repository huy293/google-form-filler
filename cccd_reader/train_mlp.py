"""
Train digit classifier dùng scikit-learn MLP
============================================
Dùng thay PyTorch khi ổ đĩa/RAM hạn chế.
MLP (Multi-Layer Perceptron) = mạng neural cơ bản, không có Conv layer.
Accuracy dự kiến: 88-93% với 15k ảnh augmented.

Để đạt 92-96% → cần PyTorch CNN (sau khi có thêm dung lượng ổ đĩa).
"""

import cv2
import numpy as np
import os
import pickle
from pathlib import Path


# ─────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────

def load_dataset(data_dir: str, img_size: int = 32):
    """Load toàn bộ ảnh từ thư mục data_dir/0/, 1/, ..., 9/"""
    X, y = [], []
    data_path = Path(data_dir)

    for digit in range(10):
        digit_dir = data_path / str(digit)
        if not digit_dir.exists():
            continue

        files = list(digit_dir.glob("*.png")) + list(digit_dir.glob("*.jpg"))
        for f in files:
            img = cv2.imread(str(f), cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue
            img = cv2.resize(img, (img_size, img_size))
            # Flatten: (32,32) → (1024,)  và normalize [0,1]
            X.append(img.flatten().astype(np.float32) / 255.0)
            y.append(digit)

    X = np.array(X)
    y = np.array(y, dtype=np.int64)
    print(f"Loaded: {X.shape[0]} samples, {np.bincount(y)} per digit")
    return X, y


# ─────────────────────────────────────────────
# TRAIN
# ─────────────────────────────────────────────

def train_mlp(data_dir: str, model_path: str = "digit_mlp.pkl"):
    """Train MLP Neural Network."""
    from sklearn.neural_network import MLPClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report

    print("Loading data...")
    X, y = load_dataset(data_dir)

    if len(X) == 0:
        print("ERROR: Khong tim thay anh nao trong", data_dir)
        return

    # Split train/test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.15, random_state=42, stratify=y
    )

    # Chuẩn hóa features
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    print(f"Train: {len(X_train)} | Test: {len(X_test)}")
    print("Training MLP... (co the mat 5-15 phut)")

    # MLP: 2 hidden layers [512, 256]
    # relu activation, adam optimizer
    clf = MLPClassifier(
        hidden_layer_sizes=(512, 256),
        activation="relu",
        solver="adam",
        alpha=0.0001,        # L2 regularization
        batch_size=128,
        learning_rate="adaptive",
        max_iter=50,
        verbose=True,
        random_state=42,
        early_stopping=True,
        validation_fraction=0.1,
        n_iter_no_change=5
    )

    clf.fit(X_train, y_train)

    # Đánh giá
    train_acc = clf.score(X_train, y_train)
    test_acc = clf.score(X_test, y_test)
    print(f"\nTrain Accuracy: {train_acc:.1%}")
    print(f"Test  Accuracy: {test_acc:.1%}")
    print("\nChi tiet theo tung so:")
    print(classification_report(y_test, clf.predict(X_test)))

    # Lưu model + scaler
    model_data = {"clf": clf, "scaler": scaler, "img_size": 32}
    with open(model_path, "wb") as f:
        pickle.dump(model_data, f)
    print(f"Model saved: {model_path}")

    return test_acc


# ─────────────────────────────────────────────
# INFERENCE
# ─────────────────────────────────────────────

class MLPDigitRecognizer:
    """Nhận dạng chữ số dùng MLP đã train."""

    def __init__(self, model_path: str = "digit_mlp.pkl"):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found: {model_path}. Chay train truoc!")
        with open(model_path, "rb") as f:
            data = pickle.load(f)
        self.clf = data["clf"]
        self.scaler = data["scaler"]
        self.img_size = data.get("img_size", 32)
        print(f"MLP model loaded: {model_path}")

    def recognize_digit(self, char_img_gray) -> tuple[str, float]:
        img = cv2.resize(char_img_gray, (self.img_size, self.img_size))
        x = img.flatten().astype(np.float32) / 255.0
        x = self.scaler.transform([x])
        probs = self.clf.predict_proba(x)[0]
        pred = int(np.argmax(probs))
        conf = float(probs[pred])
        return str(pred), conf

    def recognize_line(self, region_img) -> str:
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
            result += ch if conf > 0.4 else "?"
        return result


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python train_mlp.py train <data_dir>        <- Train model")
        print("  python train_mlp.py test <model.pkl> <img>  <- Test 1 anh")
        sys.exit(1)

    if sys.argv[1] == "train":
        data_dir = sys.argv[2] if len(sys.argv) > 2 else "data_augmented"
        train_mlp(data_dir)

    elif sys.argv[1] == "test":
        model_path = sys.argv[2]
        img_path = sys.argv[3]
        rec = MLPDigitRecognizer(model_path)
        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        pred, conf = rec.recognize_digit(img)
        print(f"Predicted: {pred} (confidence: {conf:.1%})")
