import os
from pathlib import Path
from ultralytics import YOLO

BASE_DIR = Path(__file__).resolve().parent
DATA_YAML = BASE_DIR / 'dataset' / 'data.yaml'

def train_doc_detector():
    """Huấn luyện mô hình YOLOv8n trên tập dữ liệu CCCD & Passport"""
    print("==================================================")
    print(" BẮT ĐẦU HUẤN LUYỆN MODEL YOLOv8-DOC DETECTOR")
    print("==================================================")
    
    # Load pretrained model nano (siêu nhẹ, train nhanh trên CPU/GPU)
    model = YOLO('yolov8n.pt')
    
    # Fast CPU training with high accuracy transfer learning
    results = model.train(
        data=str(DATA_YAML),
        epochs=10,
        imgsz=416,
        batch=16,
        workers=0,
        project=str(BASE_DIR / 'runs'),
        name='doc_detector_yolov8',
        exist_ok=True,
        verbose=True
    )
    
    best_weights = BASE_DIR / 'runs' / 'doc_detector_yolov8' / 'weights' / 'best.pt'
    print(f"\n[HOÀN TẤT] Model đã được huấn luyện xong! Trọng số lưu tại:\n{best_weights}")
    return best_weights

if __name__ == '__main__':
    train_doc_detector()
