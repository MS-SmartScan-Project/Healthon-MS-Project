-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: May 03, 2026 at 09:09 AM
-- Server version: 10.4.32-MariaDB
-- PHP Version: 8.2.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `ms_smartscan`
--

-- --------------------------------------------------------

--
-- Table structure for table `patients`
--

CREATE TABLE `patients` (
  `patient_id` int(100) NOT NULL,
  `full_name` varchar(100) NOT NULL,
  `birth_date` date NOT NULL,
  `gender` varchar(100) NOT NULL,
  `phone_number` varchar(100) NOT NULL,
  `status` varchar(50) DEFAULT 'لم يفحص'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `patients`
--

INSERT INTO `patients` (`patient_id`, `full_name`, `birth_date`, `gender`, `phone_number`, `status`) VALUES
(1135677453, 'فهد العتيبي', '0000-00-00', '', '0509773524', 'Infected,76.3');

-- --------------------------------------------------------

--
-- Table structure for table `scans`
--

CREATE TABLE `scans` (
  `scan_id` int(100) NOT NULL,
  `patient_id` int(100) NOT NULL,
  `scan_date` datetime(6) NOT NULL,
  `symptoms` text NOT NULL,
  `result` varchar(100) NOT NULL,
  `accuracy` int(100) NOT NULL,
  `image_path` text NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `scans`
--

INSERT INTO `scans` (`scan_id`, `patient_id`, `scan_date`, `symptoms`, `result`, `accuracy`, `image_path`) VALUES
(1, 6476476, '2026-04-02 17:58:13.000000', 'No symptoms', '', 0, 'uploads/1775141892.png'),
(2, 6476476, '2026-04-02 18:01:32.000000', 'No symptoms', '', 0, 'uploads/1775142092.png'),
(3, 6476476, '2026-04-02 18:08:43.000000', 'No symptoms recorded', 'Python was not found; run without arguments to install from the Microsoft Store, or disable this sho', 0, 'uploads/1775142523.png'),
(4, 6476476, '2026-04-02 18:10:40.000000', 'No symptoms recorded', '\'py$\' is not recognized as an internal or external command,\noperable program or batch file.', 0, 'uploads/1775142640.png'),
(5, 6476476, '2026-04-02 18:11:01.000000', 'No symptoms recorded', '\'py\' is not recognized as an internal or external command,\noperable program or batch file.', 0, 'uploads/1775142661.png'),
(6, 6476476, '2026-04-02 18:11:16.000000', 'No symptoms recorded', '\'py\' is not recognized as an internal or external command,\noperable program or batch file.', 0, 'uploads/1775142676.png'),
(7, 6476476, '2026-04-02 18:17:12.000000', 'No symptoms recorded', 'Traceback (most recent call last):\n  File \"C:\\xampp\\htdocs\\ms_smartscan\\predict.py\", line 3, in <mod', 0, 'uploads/1775143031.png'),
(8, 6476476, '2026-04-02 18:17:24.000000', 'No symptoms recorded', 'Traceback (most recent call last):\n  File \"C:\\xampp\\htdocs\\ms_smartscan\\predict.py\", line 3, in <mod', 0, 'uploads/1775143044.png'),
(9, 6476476, '2026-04-02 18:37:00.000000', 'No symptoms recorded', 'Infected', 74, 'uploads/1775144185.png'),
(10, 6476476, '2026-04-02 18:37:48.000000', 'No symptoms recorded', 'Infected', 71, 'uploads/1775144259.png'),
(11, 6476476, '2026-04-02 18:40:20.000000', 'No symptoms recorded', 'Healthy', 100, 'uploads/1775144383.png'),
(12, 6476476, '2026-04-02 18:43:37.000000', 'No symptoms recorded', 'Infected', 83, 'uploads/1775144606.png'),
(13, 6476476, '2026-04-02 18:44:17.000000', 'No symptoms recorded', 'Infected', 80, 'uploads/1775144640.png'),
(14, 6476476, '2026-04-02 19:15:00.000000', 'No symptoms recorded', 'Infected', 75, 'uploads/1775146493.png'),
(15, 6476476, '2026-04-02 19:15:01.000000', 'No symptoms recorded', 'Infected', 75, 'uploads/1775146492.png'),
(16, 6476476, '2026-04-02 19:16:59.000000', 'No symptoms recorded', 'Infected', 82, 'uploads/1775146613.png'),
(17, 6476476, '2026-04-02 19:17:01.000000', 'No symptoms recorded', 'Infected', 82, 'uploads/1775146616.png'),
(18, 6476476, '2026-04-05 11:15:11.000000', 'No symptoms recorded', 'Traceback (most recent call last):\n  File \"C:\\Users\\MAMAX\\AppData\\Local\\Programs\\Python\\Python312\\Li', 0, 'uploads/1775376907.png'),
(19, 6476476, '2026-04-05 11:21:05.000000', 'No symptoms recorded', 'Traceback (most recent call last):\n  File \"C:\\xampp\\htdocs\\ms_smartscan\\predict.py\", line 42, in <mo', 0, 'uploads/1775377259.png'),
(20, 6476476, '2026-04-05 11:23:04.000000', 'No symptoms recorded', 'خطأ تقني: HTTPCallErrorError(description=\'500 Server Error: Internal Server Error for url: https://d', 0, 'uploads/1775377380.png'),
(21, 6476476, '2026-04-05 11:29:32.000000', 'No symptoms recorded', 'حدث خطأ أثناء التحليل: HTTPCallErrorError(description=\'500 Server Error: Internal Server Error for u', 0, 'uploads/1775377766.png'),
(22, 6476476, '2026-04-05 11:32:24.000000', 'No symptoms recorded', 'حدث خطأ أثناء التحليل: HTTPCallErrorError(description=\'500 Server Error: Internal Server Error for u', 0, 'uploads/1775377938.png'),
(23, 6476476, '2026-04-05 13:28:48.000000', 'No symptoms recorded', 'النتيجة: الدماغ سليم (Normal) ✅', 0, 'uploads/1775384919.png'),
(24, 6476476, '2026-04-05 13:29:17.000000', 'No symptoms recorded', 'تنبيه: تم اكتشاف 2 إصابة (lesion) ⚠️', 0, 'uploads/1775384951.png'),
(25, 6476476, '2026-04-05 13:30:35.000000', 'No symptoms recorded', 'تنبيه: تم اكتشاف 2 مصاب (lesion) ⚠️', 0, 'uploads/1775385029.png'),
(26, 6476476, '2026-04-05 13:31:20.000000', 'No symptoms recorded', '2 مصاب (lesion) ⚠️', 0, 'uploads/1775385074.png'),
(27, 6476476, '2026-04-05 13:33:32.000000', 'No symptoms recorded', 'File \"C:\\xampp\\htdocs\\ms_smartscan\\predict.py\", line 25\n    return f\"\\u062a\\u062d\\u0644\\u064a\\u0644 ', 0, 'uploads/1775385212.png'),
(28, 6476476, '2026-04-05 13:34:15.000000', 'No symptoms recorded', 'تحليل AI: تم اكتشاف 2 بؤرة مرضية (lesion) ⚠️', 0, 'uploads/1775385248.png'),
(29, 6476476, '2026-04-20 05:37:23.000000', 'No symptoms recorded', 'خطأ تقني: HTTPCallErrorError(description=\'403 Client Error: Forbidden for url: https://detect.robofl', 0, 'uploads/1776652622.png'),
(30, 6476476, '2026-04-20 05:47:26.000000', 'No symptoms recorded', 'خطأ تقني: HTTPCallErrorError(description=\'403 Client Error: Forbidden for url: https://detect.robofl', 0, 'uploads/1776653243.png'),
(31, 6476476, '2026-04-20 05:47:57.000000', 'No symptoms recorded', 'خطأ تقني: HTTPCallErrorError(description=\'403 Client Error: Forbidden for url: https://detect.robofl', 0, 'uploads/1776653275.png'),
(32, 6476476, '2026-04-20 05:50:33.000000', 'No symptoms recorded', 'خطأ تقني: HTTPCallErrorError(description=\'403 Client Error: Forbidden for url: https://detect.robofl', 0, 'uploads/1776653430.png'),
(33, 6476476, '2026-04-20 05:50:34.000000', 'No symptoms recorded', 'خطأ تقني: HTTPCallErrorError(description=\'403 Client Error: Forbidden for url: https://detect.robofl', 0, 'uploads/1776653431.png'),
(34, 6476476, '2026-04-20 05:52:47.000000', 'No symptoms recorded', 'خطأ تقني: HTTPCallErrorError(description=\'403 Client Error: Forbidden for url: https://detect.robofl', 0, 'uploads/1776653564.png'),
(35, 6476476, '2026-04-20 05:53:03.000000', 'No symptoms recorded', 'خطأ تقني: HTTPCallErrorError(description=\'403 Client Error: Forbidden for url: https://detect.robofl', 0, 'uploads/1776653581.png'),
(36, 6476476, '2026-04-20 05:53:04.000000', 'No symptoms recorded', 'خطأ تقني: HTTPCallErrorError(description=\'403 Client Error: Forbidden for url: https://detect.robofl', 0, 'uploads/1776653582.png'),
(37, 6476476, '2026-04-20 06:18:49.000000', '', 'Traceback (most recent call last):\n  File \"C:\\xampp\\htdocs\\MS.smartScan\\predict.py\", line 3, in <mod', 0, 'uploads/1776655129.png'),
(38, 6476476, '2026-04-20 06:20:47.000000', '', 'Traceback (most recent call last):\n  File \"C:\\xampp\\htdocs\\MS.smartScan\\predict.py\", line 3, in <mod', 0, 'uploads/1776655247.png'),
(39, 6476476, '2026-04-20 06:21:00.000000', '', 'Traceback (most recent call last):\n  File \"C:\\xampp\\htdocs\\MS.smartScan\\predict.py\", line 3, in <mod', 0, 'uploads/1776655260.png'),
(40, 6476483, '2026-04-20 06:23:17.000000', '', 'Traceback (most recent call last):\n  File \"C:\\xampp\\htdocs\\MS.smartScan\\predict.py\", line 4, in <mod', 0, 'uploads/1776655396.png'),
(41, 6476483, '2026-04-20 06:28:24.000000', '', 'Creating new Ultralytics Settings v0.0.6 file  \nView Ultralytics Settings with \'yolo settings\' or at', 0, 'uploads/1776655683.png'),
(42, 6476483, '2026-04-20 06:28:24.000000', '', 'Creating new Ultralytics Settings v0.0.6 file  \nView Ultralytics Settings with \'yolo settings\' or at', 0, 'uploads/1776655687.png'),
(43, 6476483, '2026-04-20 06:28:24.000000', '', 'Creating new Ultralytics Settings v0.0.6 file  \nView Ultralytics Settings with \'yolo settings\' or at', 0, 'uploads/1776655684.png'),
(44, 6476483, '2026-04-20 06:28:24.000000', '', 'Creating new Ultralytics Settings v0.0.6 file  \nView Ultralytics Settings with \'yolo settings\' or at', 0, 'uploads/1776655686.png'),
(45, 6476483, '2026-04-20 06:28:24.000000', '', 'Creating new Ultralytics Settings v0.0.6 file  \nView Ultralytics Settings with \'yolo settings\' or at', 0, 'uploads/1776655687.png'),
(46, 6476483, '2026-04-20 06:28:24.000000', '', 'Creating new Ultralytics Settings v0.0.6 file  \nView Ultralytics Settings with \'yolo settings\' or at', 0, 'uploads/1776655680.png'),
(47, 6476483, '2026-04-20 06:28:33.000000', '', 'image 1/1 C:\\xampp\\htdocs\\MS.smartScan\\uploads\\1776655709.png: 480x640 2 Objects, 72.2ms\nSpeed: 1.5m', 0, 'uploads/1776655709.png'),
(48, 6476483, '2026-04-20 06:28:36.000000', '', 'image 1/1 C:\\xampp\\htdocs\\MS.smartScan\\uploads\\1776655713.png: 480x640 2 Objects, 60.4ms\nSpeed: 3.4m', 0, 'uploads/1776655713.png'),
(49, 6476482, '2026-04-20 06:30:12.000000', '', 'Infected', 0, 'uploads/1776655809.png'),
(50, 6476483, '2026-04-20 06:34:50.000000', '', 'Infected', 0, 'uploads/1776656087.png'),
(51, 324432, '2026-04-20 06:40:02.000000', '', 'Infected', 0, 'uploads/1776656399.png'),
(52, 6476483, '2026-04-20 06:43:32.000000', '', 'Infected', 0, 'uploads/1776656608.png'),
(53, 6476483, '2026-04-20 06:43:47.000000', '', 'Infected', 0, 'uploads/1776656624.png'),
(54, 6476483, '2026-04-20 06:46:22.000000', '', 'Infected', 0, 'uploads/1776656779.png'),
(55, 6476483, '2026-04-20 06:46:37.000000', '', 'Infected', 0, 'uploads/1776656794.png'),
(56, 6476480, '2026-04-20 06:46:54.000000', '', 'Healthy', 0, 'uploads/1776656811.png'),
(57, 6476483, '2026-04-20 06:56:32.000000', '', 'Infected', 0, 'uploads/1776657389.png'),
(58, 6476482, '2026-04-20 06:58:17.000000', '', 'Infected', 0, 'uploads/1776657494.png'),
(59, 6476481, '2026-04-20 06:58:35.000000', '', 'Infected', 0, 'uploads/1776657512.png'),
(60, 324432, '2026-04-20 06:59:10.000000', '', 'Infected', 0, 'uploads/1776657547.png'),
(61, 324432, '2026-04-20 07:01:16.000000', '', 'Infected', 0, 'uploads/1776657673.png'),
(62, 324432, '2026-04-20 07:01:32.000000', '', 'Infected', 0, 'uploads/1776657689.png'),
(63, 324432, '2026-04-20 07:01:51.000000', '', 'Infected', 0, 'uploads/1776657708.png'),
(64, 6476481, '2026-04-20 07:04:00.000000', '', 'Infected', 0, 'uploads/1776657837.png'),
(65, 6476483, '2026-04-20 07:04:22.000000', '', 'Infected', 0, 'uploads/1776657859.png'),
(66, 6476483, '2026-04-20 07:06:02.000000', '', 'Infected', 0, 'uploads/1776657958.png'),
(67, 6476483, '2026-04-20 07:06:17.000000', '', 'Infected', 0, 'uploads/1776657974.png'),
(68, 6476483, '2026-04-20 07:07:13.000000', '', 'Infected', 0, 'uploads/1776658030.png'),
(69, 6476483, '2026-04-20 07:07:35.000000', '', 'Infected', 0, 'uploads/1776658052.png'),
(70, 665877, '2026-04-20 07:07:49.000000', '', 'Infected', 0, 'uploads/1776658066.png'),
(71, 665877, '2026-04-20 07:10:43.000000', '', 'Infected,80.6', 0, 'uploads/1776658240.png'),
(72, 6476483, '2026-04-25 04:38:41.000000', '', 'Infected,87.1', 0, 'uploads/1777081097.png'),
(73, 113455694, '2026-04-26 15:20:22.000000', '', 'Infected,84.5', 0, 'uploads/1777205993.png'),
(74, 1135677453, '2026-04-27 09:12:59.000000', '', 'Infected,83.3', 0, 'uploads/1777270370.png'),
(75, 1135677453, '2026-04-27 09:13:28.000000', '', 'Infected,76.3', 0, 'uploads/1777270404.png');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `patients`
--
ALTER TABLE `patients`
  ADD PRIMARY KEY (`patient_id`);

--
-- Indexes for table `scans`
--
ALTER TABLE `scans`
  ADD PRIMARY KEY (`scan_id`),
  ADD KEY `رقم _المريض` (`patient_id`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `patients`
--
ALTER TABLE `patients`
  MODIFY `patient_id` int(100) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=1135677454;

--
-- AUTO_INCREMENT for table `scans`
--
ALTER TABLE `scans`
  MODIFY `scan_id` int(100) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=76;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
