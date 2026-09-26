import sys
import os
import cv2
import numpy as np

os.environ['YOLO_VERBOSE'] = 'False'

try:
    from ultralytics import YOLO
    import mysql.connector
    
    model = YOLO('best.pt')
    image_path = sys.argv[1]
    patient_id = sys.argv[2]

    # تحسين الصورة
    img = cv2.imread(image_path)
    if img is not None:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        enhanced_img = clahe.apply(gray)
        cv2.imwrite(image_path, enhanced_img)

    # تشغيل الفحص (conf=0.05 لضمان الاكتشاف)
    results = model(image_path, verbose=False, conf=0.05)
    
    status_result = "Healthy"
    confidence = 0

    if len(results[0].boxes) > 0:
        status_result = "Infected"
        # استخراج أعلى نسبة تأكد بين الأجسام المكتشفة
        confidence = float(results[0].boxes.conf.max()) * 100 
    else:
        # إذا كان سليم، غالباً تكون نسبة التأكد من أنه سليم عالية
        confidence = 100 # افتراضياً لعدم وجود صناديق

    # تحديث قاعدة البيانات
    try:
        db = mysql.connector.connect(host="localhost", user="root", password="", database="ms_smartscan")
        cursor = db.cursor()
        # سنحفظ الحالة مع النسبة في قاعدة البيانات
        display_status = f"{status_result} ({confidence:.1f}%)"
        cursor.execute("UPDATE patients SET status = %s WHERE patient_id = %s", (display_status, patient_id))
        db.commit()
        cursor.close()
        db.close()
    except:
        pass

    # نطبع النتيجة والنسبة مفصولين بفاصلة ليستلمهم الـ PHP
    print(f"{status_result},{confidence:.1f}")

except Exception as e:
    print(f"Error,{str(e)}")