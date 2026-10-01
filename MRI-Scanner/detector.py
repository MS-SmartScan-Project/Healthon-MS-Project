"""
محرك التحليل — النموذج يُحمَّل مرة واحدة فقط فيكون كل فحص أسرع بكثير.

الخطوات:
  1) قراءة الصورة وتحويلها إلى رمادي
  2) تشغيل best.pt على الصورة الرمادية **بدون CLAHE** بحد ثقة conf=0.05
     (CLAHE كان يُخفي البؤر الحقيقية؛ يُستخدم الآن لصورة العرض "Enhanced" فقط)
     النموذج يُشغَّل بحجمين (320 و 640): يبدو أنه دُرّب على صور صغيرة، فبعض البؤر لا تظهر له إلا بالحجم الصغير.
  3) تجاهل الصناديق الكبيرة جداً (> 15% من الصورة): النموذج يرسم أحياناً مربعاً حول الدماغ كله،
     وهذا ليس آفة. تُحفظ هذه الصناديق للمراجعة لكنها لا تُحتسب في النتيجة.
     الصناديق المتكررة لنفس البؤرة من الحجمين تُدمج في صندوق واحد (بأعلى ثقة).
  4) إذا بقيت صناديق بؤرية → Infected + أعلى نسبة ثقة، وإلا → Healthy دون ثقة مصطنعة
"""
import os
import threading

import cv2

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "best.pt")
CONF = 0.05          # نفس قيمة predict.py
IMAGE_SIZES = (320, 640)   # 640 = حجم التدريب المحفوظ في النموذج؛ 320 يكشف بؤراً يفوّتها 640
MAX_LESION_AREA = 0.15   # آفة MS بقعة صغيرة؛ صندوق يغطي أكثر من 15% من الصورة = الدماغ كله، لا آفة


def merge_duplicates(boxes):
    """Keep one box per lesion: drop a box that mostly overlaps a stronger one (found at the other size)."""
    kept = []
    for b in sorted(boxes, key=lambda x: x["conf"], reverse=True):
        x1, y1, x2, y2 = b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"]
        duplicate = False
        for k in kept:
            ix = max(0.0, min(x2, k["x"] + k["w"]) - max(x1, k["x"]))
            iy = max(0.0, min(y2, k["y"] + k["h"]) - max(y1, k["y"]))
            inter = ix * iy
            smaller = min(b["w"] * b["h"], k["w"] * k["h"]) or 1e-9
            if inter / smaller > 0.5:
                duplicate = True
                break
        if not duplicate:
            kept.append(b)
    return kept
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
    """Grayscale image for the model, plus a CLAHE copy saved only for the 'Enhanced' viewer layer."""
    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("تعذّرت قراءة الصورة")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    if enhanced_path and not cv2.imwrite(enhanced_path, enhanced):
        raise OSError("تعذّر حفظ الصورة المحسّنة")
    return gray, enhanced


def analyze(image_path, enhanced_path, annotated_path):
    """يحلل الصورة ويرجع النتيجة + أماكن البؤر، ويحفظ نسخة مرسوم عليها المربعات."""
    if _model is None:
        raise RuntimeError(_error or "النموذج غير محمّل")

    gray, enhanced = enhance(image_path, enhanced_path)
    model_input = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)      # بدون CLAHE — انظر الوصف أعلاه
    with _lock:
        # TTA checks scaled/flipped views and improves robustness across camera/upload sources.
        results = [_model(model_input, verbose=False, conf=CONF, imgsz=size, augment=True)[0] for size in IMAGE_SIZES]

    boxes, ignored = [], []
    h, w = gray.shape[:2]
    for r in results:
        for b in r.boxes:
            x1, y1, x2, y2 = [float(v) for v in b.xyxy[0].tolist()]
            box = {
                "x": x1 / w, "y": y1 / h, "w": (x2 - x1) / w, "h": (y2 - y1) / h,
                "conf": round(float(b.conf[0]) * 100, 1),
            }
            # الخطوة 3 — صندوق بحجم الدماغ ليس آفة
            (ignored if box["w"] * box["h"] > MAX_LESION_AREA else boxes).append(box)
    boxes, ignored = merge_duplicates(boxes), merge_duplicates(ignored)

    # الخطوة 4
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
        "ignored_boxes": ignored,     # whole-brain regions, kept for audit only
        "tta": True,
        "image_sizes": list(IMAGE_SIZES),
    }
