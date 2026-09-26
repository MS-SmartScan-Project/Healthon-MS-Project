<?php
$host = "localhost";
$user = "root";
$pass = "";
$db   = "ms_smartscan";

$conn = new mysqli($host, $user, $pass, $db);

if ($conn->connect_error) {
    die("Connection failed: " . $conn->connect_error);
}

// ضروري جداً لظهور الأسماء العربية للمرضى بشكل صحيح
$conn->set_charset("utf8mb4"); 
?>