<?php
include "connect.php";
if (!isset($_GET['id'])) { header("Location: index.php"); exit(); }
$patient_id = $_GET['id'];
$sql = "SELECT * FROM patients WHERE patient_id = '$patient_id'";
$res = $conn->query($sql);
$patient = $res->fetch_assoc();
?>
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>وحدة الفحص الذكي</title>
    <link rel="stylesheet" href="style.css">
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap" rel="stylesheet">
</head>
<body>
    <div class="container">
        <div class="card scan-card">
            <h2>فحص المريض: <?php echo $patient['full_name']; ?></h2>
            
            <div class="camera-wrapper">
                <div id="camera-permission" class="overlay">
                    <p>الموقع يحتاج الوصول للكاميرا لبدء الفحص</p>
                    <button onclick="startCamera()" class="btn-add">تشغيل الكاميرا</button>
                </div>
                
                <div class="video-container">
                    <video id="video" autoplay playsinline></video>
                </div>
                <canvas id="canvas" style="display:none;"></canvas>
            </div>

            <div class="controls">
                <button id="capture-btn" class="btn-scan" disabled>إلتقاط الصورة وتحليلها</button>
                <a href="index.php" id="back-link" class="btn-secondary">إلغاء</a>
            </div>
            
            <div id="result-area" style="display:none; margin-top:20px; padding:20px; border-radius:15px; border: 2px solid;">
                <h3 id="result-text"></h3>
                <p id="result-info">تم حفظ التشخيص في ملف المريض بنجاح.</p>
                <br>
                <a href="index.php" class="btn-add" style="text-decoration: none; display: inline-block;">العودة لجدول المرضى</a>
            </div>
        </div>
    </div>

    <script>
        const video = document.getElementById('video');
        const canvas = document.getElementById('canvas');
        const captureBtn = document.getElementById('capture-btn');
        const resultArea = document.getElementById('result-area');
        const resultText = document.getElementById('result-text');
        const backLink = document.getElementById('back-link');

        // 1. تشغيل الكاميرا
        function startCamera() {
            navigator.mediaDevices.getUserMedia({ video: true })
                .then(stream => {
                    video.srcObject = stream;
                    document.getElementById('camera-permission').style.display = 'none';
                    captureBtn.disabled = false;
                })
                .catch(err => alert("عذراً، يجب السماح بالكاميرا"));
        }

        // 2. معالجة الإلتقاط واستقبال النتيجة مع نسبة التأكد
        captureBtn.addEventListener('click', () => {
            captureBtn.disabled = true;
            captureBtn.innerText = "جاري التحليل...";

            const context = canvas.getContext('2d');
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            context.drawImage(video, 0, 0);
            const imageData = canvas.toDataURL('image/png');

            const formData = new FormData();
            formData.append('image', imageData);
            formData.append('patient_id', '<?php echo $patient_id; ?>');

            fetch('save_scan.php', { method: 'POST', body: formData })
            .then(response => response.text())
            .then(data => {
                // التقسيم لاستخراج الحالة والنسبة (مثل: Infected,85.5)
                const parts = data.split(',');
                const status = parts[0].trim();
                const confidence = parts[1] ? parts[1].trim() : "0";

                captureBtn.style.display = 'none';
                backLink.style.display = 'none';
                resultArea.style.display = 'block';

                if (status === 'Infected') {
                    resultArea.style.backgroundColor = '#ffd7d7';
                    resultArea.style.borderColor = '#c0392b';
                    resultText.style.color = '#c0392b';
                    resultText.innerHTML = "التشخيص: Infected <br><small style='color:#333'>نسبة التأكد: " + confidence + "%</small>";
                } else {
                    resultArea.style.backgroundColor = '#d7ffd7';
                    resultArea.style.borderColor = '#27ae60';
                    resultText.style.color = '#27ae60';
                    resultText.innerHTML = "التشخيص: Healthy <br><small style='color:#333'>نسبة اليقين: " + confidence + "%</small>";
                }
            });
        });
    </script>
</body>
</html>