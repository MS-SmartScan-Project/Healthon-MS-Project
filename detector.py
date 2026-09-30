"""
محرك التحليل — نفس خطوات predict.py بالضبط، لكن النموذج يُحمَّل مرة واحدة فقط
فيكون كل فحص أسرع بكثير.

خطوات predict.py:
  1) قراءة الصورة وتحويلها إلى رمادي
  2) تحسين التباين بخوارزمية CLAHE (clipLimit=3.0, tileGridSize=8x8)
  3) تشغيل best.pt بحد ثقة conf=0.05
  4) إذا وُجدت صناديق → Infected + أعلى نسبة ثقة، وإلا → Healthy دون ثقة مصطنعة
"""
import os
import threading

import cv2

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "best.pt")
CONF = 0.05          # نفس قيمة predict.py
IMAGE_SIZE = 640     # نفس حجم التدريب المحفوظ داخل النموذج
_model = None
_lock = threading.Lock()
_error = None


def load_model():
    """يحمّل best.pt (يُستدعى مرة واحدة عند تشغيل السيرفر)."""
    global _model, _error
    try:
        os.environ["YOLO_VERBOSE"] = "False"
        from ultralytics import YOLO
        _model = YOLO(MODEL_PATH)
        _error = None
    except Exception as e:  # مكتبة ناقصة أو ملف تالف
        _error = str(e)
    return _model is not None


def status():
    if _model is not None:
        return {"ready": True, "error": None}
    return {"ready": False, "error": _error}


def enhance(image_path, enhanced_path=None):
    """Convert to grayscale and apply CLAHE without changing the source image."""
    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("تعذّرت قراءة الصورة")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    if enhanced_path and not cv2.imwrite(enhanced_path, enhanced):
        raise OSError("تعذّر حفظ الصورة المحسّنة")
    return enhanced


def analyze(image_path, enhanced_path, annotated_path):
    """يحلل الصورة ويرجع النتيجة + أماكن البؤر، ويحفظ نسخة مرسوم عليها المربعات."""
    if _model is None:
        raise RuntimeError(_error or "النموذج غير محمّل")

    enhanced = enhance(image_path, enhanced_path)
    model_input = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
    with _lock:
        # TTA checks scaled/flipped views and improves robustness across camera/upload sources.
        results = _model(model_input, verbose=False, conf=CONF, imgsz=IMAGE_SIZE, augment=True)

    boxes = []
    r = results[0]
    h, w = enhanced.shape[:2]
    for b in r.boxes:
        x1, y1, x2, y2 = [float(v) for v in b.xyxy[0].tolist()]
        boxes.append({
            "x": x1 / w, "y": y1 / h, "w": (x2 - x1) / w, "h": (y2 - y1) / h,
            "conf": round(float(b.conf[0]) * 100, 1),
        })

    # الخطوة 4 — نفس منطق predict.py
    if boxes:
        result = "Infected"
        confidence = max(b["conf"] for b in boxes)
    else:
        result = "Healthy"
        confidence = None

    # نسخة للعرض مرسوم عليها مربعات البؤر
    canvas = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
    thick = max(2, round(min(w, h) / 250))
    for b in boxes:
        p1 = (int(b["x"] * w), int(b["y"] * h))
        p2 = (int((b["x"] + b["w"]) * w), int((b["y"] + b["h"]) * h))
        cv2.rectangle(canvas, p1, p2, (94, 63, 244), thick)        # وردي/أحمر
        label = f'{b["conf"]:.0f}%'
        scale = max(0.5, min(w, h) / 900)
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
        cv2.rectangle(canvas, (p1[0], p1[1] - th - 8), (p1[0] + tw + 8, p1[1]), (94, 63, 244), -1)
        cv2.putText(canvas, label, (p1[0] + 4, p1[1] - 5), cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 1, cv2.LINE_AA)
    if not cv2.imwrite(annotated_path, canvas):
        raise OSError("تعذّر حفظ الصورة المعلّمة")

    return {
        "result": result,
        "confidence": round(confidence, 1) if confidence is not None else None,
        "boxes": boxes,
        "tta": True,
        "image_size": IMAGE_SIZE,
    }
