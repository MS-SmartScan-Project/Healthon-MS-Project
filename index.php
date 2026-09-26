<?php
include "connect.php";

// جلب قائمة المرضى
$sql_patients = "SELECT * FROM patients ORDER BY patient_id DESC";
$result_patients = $conn->query($sql_patients);

// إضافة مريض جديد
if (isset($_POST['add_patient'])) {

    $patient_id = $conn->real_escape_string($_POST['id']);
    $patient_name = $conn->real_escape_string($_POST['name']);
    $patient_gender = $conn->real_escape_string($_POST['gender']);
    $patient_phone = $conn->real_escape_string($_POST['phone']);

    // 1. فحص هل المريض موجود مسبقاً لمنع الـ Fatal Error
    $check_sql = "SELECT patient_id FROM patients WHERE patient_id = '$patient_id'";
    $check_result = $conn->query($check_sql);

    if ($check_result && $check_result->num_rows > 0) {
        // المريض موجود فعلاً -> نرسل exists=1 في الرابط
        header("Location: index.php?exists=1");
        exit();
    } else {
        // 2. إذا لم يكن موجوداً، نقوم بالإدخال
        $sql_insert = "INSERT INTO patients (patient_id, full_name, gender, phone_number)
                       VALUES ('$patient_id', '$patient_name', '$patient_gender', '$patient_phone')";

        if ($conn->query($sql_insert) === TRUE) {
            header("Location: index.php?success=1");
            exit();
        } else {
            // في حال وجود خطأ تقني آخر غير التكرار
            header("Location: index.php?error=1");
            exit();
        }
    }
}
?>

<!DOCTYPE html>
<html lang="ar" dir="rtl">

<head>

    <meta charset="UTF-8">

    <title>إدارة المرضى - MS SmartScan</title>

    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap" rel="stylesheet">

    <link rel="stylesheet" href="style.css">

</head>

<body>

<!-- حالة النظام -->
<div class="system-status">

    <span class="status-dot"></span>

    <span class="status-text">System Online</span>

</div>

<!-- رسائل -->
<?php if(isset($_GET['success'])): ?>
<div class="success-message">✔ تم حفظ بيانات المريض بنجاح</div>
<?php endif; ?>

<?php if(isset($_GET['error'])): ?>
<div class="error-message">❌ حدث خطأ أثناء حفظ البيانات </div>
<?php endif; ?>
<?php if(isset($_GET['exists'])): ?>
<div class="exists-message">❌ المريض مسجل مسبقاً</div>
<?php endif; ?>

<!-- واجهة البداية تظهر فقط أول مرة -->
<?php if(!isset($_GET['success']) && !isset($_GET['error']) && !isset($_GET['exists'])): ?>

<div id="welcome-overlay" class="welcome-overlay">

    <div class="welcome-content">

        <h1>MS SmartScan</h1>

        <p>
            نظام ذكي متكامل للكشف التلقائي عن بؤر التصلب المتعدد (MS)
            في صور الرنين المغناطيسي وتصنيف الحالة فورياً.
        </p>

        <div class="intro-steps">

            <span>🧠 تحليل بالذكاء الاصطناعي</span>

            <span>📂 أرشفة فورية للنتائج</span>

            <span>📷 فحص حي عبر الكاميرا</span>

        </div>

        <button onclick="closeWelcome()" class="btn-start-now">

            ابدأ إدارة المرضى

        </button>

    </div>

</div>

<?php endif; ?>


<div class="container">

    <!-- تسجيل مريض -->
    <div class="card">

        <h2>تسجيل مريض جديد</h2>

        <form method="POST">

            <input type="text" name="id" placeholder="الرقم الطبي (ID)" required>

            <input type="text" name="name" placeholder="اسم المريض بالكامل" required>

            <select name="gender" required>

                <option value="" disabled selected>اختر الجنس</option>

                <option value="ذكر">ذكر</option>

                <option value="أنثى">أنثى</option>

            </select>

            <input type="text" name="phone" placeholder="رقم الهاتف" required>

            <button type="submit" name="add_patient" class="btn-add">

                حفظ البيانات

            </button>

        </form>

    </div>


    <!-- قائمة المرضى -->
    <div class="card">

        <h2>قائمة المرضى ونتائج الفحص</h2>

        <table>

            <thead>

                <tr>

                    <th>رقم المريض</th>

                    <th>اسم المريض</th>

                    <th>آخر تشخيص</th>

                    <th>خيارات</th>

                </tr>

            </thead>

            <tbody>

            <?php

            if ($result_patients && $result_patients->num_rows > 0) {

                while($row = $result_patients->fetch_assoc()) {

                    $status = $row['status'] ?? 'لم يفحص';

                    if (
                        strpos($status, 'Infected') !== false ||
                        strpos($status, 'بؤرة') !== false ||
                        strpos($status, '⚠️') !== false
                    ) {

                        $statusClass = 'status-infected';

                    } elseif (
                        strpos($status, 'Healthy') !== false ||
                        strpos($status, 'سليم') !== false
                    ) {

                        $statusClass = 'status-healthy';

                    } else {

                        $statusClass = 'status-none';
                    }

                    echo "<tr>";

                    echo "<td>#".$row['patient_id']."</td>";

                    echo "<td>".$row['full_name']."</td>";

                    echo "<td>
                    <span class='status-badge $statusClass'>
                    ".$status."
                    </span>
                    </td>";

                    echo "<td>
                    <a href='scan.php?id=".$row['patient_id']."' class='btn-scan'>
                    إجراء فحص
                    </a>
                    </td>";

                    echo "</tr>";
                }

            } else {

                echo "
                <tr>
                    <td colspan='4' style='text-align:center;'>
                    لا يوجد مرضى مسجلين
                    </td>
                </tr>";
            }

            ?>

            </tbody>

        </table>

    </div>

</div>


<script>

function closeWelcome() {

    document.getElementById('welcome-overlay').style.display = 'none';
}

</script>

</body>

</html>