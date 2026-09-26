<?php
include "connect.php";

/* 1. استلام البيانات */
$data = $_POST['image'] ?? '';
$patient_id = $_POST['patient_id'] ?? '';

if (empty($data)) die("خطأ: لم يتم استلام صورة");

/* 2. حفظ الصورة */
$data = preg_replace('#^data:image/\w+;base64,#i', '', $data);
$data = base64_decode($data);
$file_path = "uploads/" . time() . ".png";
if(!file_exists('uploads')) mkdir('uploads', 0777, true);
file_put_contents($file_path, $data);

/* 3. تشغيل البايثون (YOLOv11m) */
$command = "python predict.py \"$file_path\" \"$patient_id\" 2>&1";
$output = shell_exec($command);
$result = trim($output); // النتيجة المتوقعة مثل: Infected 26%

// --- المنطق الجديد: فلترة النتائج أقل من 70% ---
$final_status = $result; 

// نبحث عن أي أرقام داخل النص الراجع من بايثون
preg_match('/\d+/', $result, $matches);
$confidence_value = isset($matches[0]) ? intval($matches[0]) : 0;

// إذا كانت النتيجة تحتوي على Infected والنسبة أقل من 70
if (stripos($result, 'Infected') !== false && $confidence_value < 70) {
    $final_status = "Healthy"; 
}
// ----------------------------------------------

$safe_result = mysqli_real_escape_string($conn, $final_status);

/* 4. تحديث البيانات */
// حفظ الفحص في سجل الفحوصات
$conn->query("INSERT INTO scans (patient_id, image_path, result, scan_date) VALUES ('$patient_id', '$file_path', '$safe_result', NOW())");

// تحديث حالة المريض بالنتيجة المفلترة
$update_sql = "UPDATE patients SET status = '$safe_result' WHERE patient_id = '$patient_id'";

if(!$conn->query($update_sql)){
    echo $final_status;
} else {
    echo $final_status;
}
?>
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>نتيجة فحص MS SmartScan</title>
    <link rel="stylesheet" href="style.css">
    <style>
        .result-box {
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            text-align: center;
            max-width: 500px;
            margin: 50px auto;
        }
        .healthy { color: #27ae60; font-weight: bold; }
        .warning { color: #e74c3c; font-weight: bold; }
    </style>
</head>
<body>

    <div class="result-box">
        <h1>نتيجة فحص MS SmartScan</h1>
        <hr>
        <h3>التشخيص النهائي:</h3>
        
        <?php if (strtolower($result) == 'normal'): ?>
            <h2 class="healthy">الحالة سليمة (Normal) ✅</h2>
            <p>لم يتم اكتشاف أي بؤر مرضية في الصورة.</p>
        <?php else: ?>
            <h2 class="warning">تم اكتشاف: <?php echo $result; ?> ⚠️</h2>
            <p>ينصح بمراجعة الطبيب المختص لمتابعة النتائج.</p>
        <?php endif; ?>

        <div style="margin-top: 30px;">
            <img src="<?php echo $file_path; ?>" alt="صورة الفحص" style="max-width: 100%; border-radius: 10px;">
        </div>

        <br>
        <a href="dashboard.php" class="btn-scan">العودة للوحة التحكم</a>
    </div>

</body>
</html>