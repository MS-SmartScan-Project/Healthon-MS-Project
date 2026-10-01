/* MS SmartScan — English / Arabic switch (shared by the MRI Scanner and the Patient Registry)
 *
 * The pages are written in English. In Arabic mode every visible English text is swapped for its
 * translation below (also text added later by the page scripts, e.g. results and messages), the page
 * turns right-to-left, and switching back restores the original English.
 * To fix or add a translation, edit the AR dictionary: "English text exactly as shown": "Arabic".
 */
(() => {
  const AR = {
    // ---------- shared / header ----------
    'MS SmartScan · AI-Assisted MS Lesion Screening': 'MS SmartScan · الكشف عن آفات التصلب المتعدد بمساعدة الذكاء الاصطناعي',
    'MS SmartScan home': 'الصفحة الرئيسية لـ MS SmartScan',
    'MS SmartScan logo': 'شعار MS SmartScan',
    'Sections': 'الأقسام',
    'Workspace': 'مساحة العمل',
    'Technology': 'التقنية',
    'Images and records are processed and stored only on this device': 'تُعالَج الصور والسجلات وتُحفظ على هذا الجهاز فقط',
    'On-device': 'على الجهاز',
    'Loading AI model…': 'جارٍ تحميل النموذج…',
    'Clinician workstation': 'محطة عمل الطبيب',
    'Clinician': 'الطبيب',
    'Neurology · Radiology': 'الأعصاب · الأشعة',
    'AI model ready': 'النموذج جاهز',
    'YOLO11n · best.pt loaded': 'YOLO11n · تم تحميل best.pt',
    'Model unavailable': 'النموذج غير متاح',
    'Switch language': 'تغيير اللغة',

    // ---------- scanner: hero ----------
    'AI clinical decision support · Multiple Sclerosis': 'دعم القرار السريري بالذكاء الاصطناعي · التصلب المتعدد',
    'Screen MRI scans for': 'فحص صور الرنين المغناطيسي بحثاً عن',
    'MS-related lesions': 'آفات التصلب المتعدد',
    'in seconds.': 'خلال ثوانٍ.',
    "MS SmartScan gives neurologists and radiologists a second pair of eyes: it enhances the MRI, localizes suspicious lesions with a trained YOLO11 model, and stores every result in the patient's record — entirely on-device.":
      'يمنح MS SmartScan أطباء الأعصاب وأخصائيي الأشعة عيناً ثانية: يحدد الآفات المشتبهة في صورة الرنين بنموذج YOLO11 مدرَّب، ويحفظ كل نتيجة في سجل المريض — بالكامل على الجهاز.',
    'Start a new scan': 'بدء فحص جديد',
    'How it works': 'كيف يعمل',
    'Precision': 'الدقة',
    'Recall': 'الحساسية',
    'Avg. analysis': 'متوسط التحليل',
    'Validation-set metrics recorded in the model file (best.pt). Analysis time is measured live on this device.':
      'مقاييس بيانات التحقق مسجّلة في ملف النموذج (best.pt). زمن التحليل يُقاس مباشرة على هذا الجهاز.',
    'Focal lesion check': 'فحص البؤر',
    'Whole-brain regions ignored': 'تجاهل المناطق بحجم الدماغ كاملاً',
    'Lesion localization': 'تحديد موقع الآفات',
    'YOLO11n · on-device': 'YOLO11n · على الجهاز',

    // ---------- scanner: workspace ----------
    'Clinical workspace': 'مساحة العمل السريرية',
    'New MRI screening': 'فحص رنين جديد',
    "Register the patient, add the MRI image, and run the AI analysis. The result is saved to the patient's record automatically.":
      'أدخل بيانات المريض، وأضف صورة الرنين، ثم شغّل تحليل الذكاء الاصطناعي. تُحفظ النتيجة في سجل المريض تلقائياً.',
    'For qualified clinicians.': 'للأطباء المؤهلين فقط.',
    'Results are AI decision support, not a diagnosis. Patient data never leaves this device.':
      'النتائج دعم للقرار بالذكاء الاصطناعي وليست تشخيصاً. بيانات المرضى لا تغادر هذا الجهاز.',
    'Acknowledge': 'موافق',
    'Workflow progress': 'مراحل الفحص',
    'Patient': 'المريض',
    'Name & medical number': 'الاسم والرقم الطبي',
    'MRI image': 'صورة الرنين',
    'Upload or capture': 'رفع أو تصوير',
    'AI analysis': 'تحليل الذكاء الاصطناعي',
    'YOLO11n + focal check': 'YOLO11n + فحص البؤر',
    'Finding': 'النتيجة',
    'Result & next step': 'النتيجة والخطوة التالية',
    'Record': 'السجل',
    'Saved to registry': 'يُحفظ في السجل',
    'Patient information': 'بيانات المريض',
    'Required': 'إلزامي',
    'Patient name': 'اسم المريض',
    'Full name': 'الاسم الكامل',
    'Medical number': 'الرقم الطبي',
    'Unique patient identifier': 'معرّف فريد للمريض',
    'e.g. MRN-10024': 'مثال: MRN-10024',
    'Image source': 'مصدر الصورة',
    'Upload': 'رفع',
    'Camera': 'الكاميرا',
    'Drop the MRI image here': 'اسحب صورة الرنين وأفلتها هنا',
    'or': 'أو',
    'browse files': 'تصفّح الملفات',
    '· PNG, JPG, WebP, BMP · up to 10 MB': '· PNG، JPG، WebP، BMP · حتى 10 ميجابايت',
    'Point the Raspberry Pi camera at the MRI film or screen, keep it steady, and use even backlighting.':
      'وجّه كاميرا Raspberry Pi نحو فيلم الرنين أو الشاشة، وثبّتها، واستخدم إضاءة خلفية متساوية.',
    'Start camera': 'تشغيل الكاميرا',
    'Restart camera': 'إعادة تشغيل الكاميرا',
    'Select camera': 'اختيار الكاميرا',
    'Remove image': 'إزالة الصورة',
    'Run AI analysis': 'تشغيل تحليل الذكاء الاصطناعي',
    'Capture & analyze': 'التقاط وتحليل',
    'Waiting for AI model…': 'بانتظار النموذج…',
    'New image · same patient': 'صورة جديدة · نفس المريض',
    'New patient': 'مريض جديد',
    'All three are required: patient name, medical number, and MRI image.': 'الثلاثة إلزامية: اسم المريض، والرقم الطبي، وصورة الرنين.',

    // ---------- scanner: viewer ----------
    'MRI Viewer': 'عارض الرنين',
    'No patient selected': 'لم يُحدَّد مريض',
    'Unnamed': 'بدون اسم',
    'Awaiting image': 'بانتظار الصورة',
    'Ready to analyze': 'جاهز للتحليل',
    'Live camera': 'الكاميرا مباشرة',
    'Analyzing': 'جارٍ التحليل',
    'Duplicate rejected': 'مرفوض (مكرر)',
    'Analysis failed': 'فشل التحليل',
    'No MRI loaded': 'لا توجد صورة رنين',
    'Upload an image or start the camera to begin.': 'ارفع صورة أو شغّل الكاميرا للبدء.',
    'Analyzing MRI…': 'جارٍ تحليل صورة الرنين…',
    'AI-assisted screening in progress ·': 'الفحص بالذكاء الاصطناعي جارٍ ·',
    'Image layer': 'طبقة الصورة',
    'AI overlay': 'تحديد الآفات',
    'Enhanced': 'محسّنة',
    'Original': 'الأصلية',
    'Zoom': 'التكبير',
    'Zoom out': 'تصغير',
    'Zoom in': 'تكبير',
    'Fit to view': 'ملاءمة العرض',
    'Fit': 'ملاءمة',
    'Medical no.': 'الرقم الطبي',
    'Scan status': 'حالة الصورة',
    'No image': 'لا توجد صورة',
    'Loaded': 'تم التحميل',
    'Captured': 'تم الالتقاط',
    'Analysis': 'التحليل',
    'Not started': 'لم يبدأ',
    'In progress': 'قيد التنفيذ',
    'Rejected': 'مرفوض',
    'Failed': 'فشل',
    'AI result': 'نتيجة الذكاء الاصطناعي',
    'AI confidence': 'ثقة الذكاء الاصطناعي',
    'N/A': 'غير منطبق',
    'Camera capture': 'صورة من الكاميرا',

    // ---------- scanner: finding ----------
    'AI finding appears here': 'تظهر نتيجة الذكاء الاصطناعي هنا',
    "After analysis you will see the finding, the model's confidence, and the recommended next clinical step.":
      'بعد التحليل ستظهر النتيجة، ونسبة ثقة النموذج، والخطوة السريرية التالية الموصى بها.',
    'Image sent securely to local AI engine': 'أُرسلت الصورة بأمان إلى محرك الذكاء الاصطناعي المحلي',
    'YOLO11n inference and focal-lesion check': 'تحليل YOLO11n وفحص البؤر',
    'Result saved to patient record': 'حُفظت النتيجة في سجل المريض',
    'AI finding': 'نتيجة الذكاء الاصطناعي',
    '70% review threshold': 'حد المراجعة 70%',
    'Regions flagged': 'المناطق المحددة',
    'Analysis time': 'زمن التحليل',
    'AI-assisted screening result. Final diagnosis requires clinical assessment and appropriate diagnostic criteria.':
      'نتيجة فحص بمساعدة الذكاء الاصطناعي. يتطلب التشخيص النهائي تقييماً سريرياً ومعايير تشخيصية مناسبة.',
    'Suspicious lesion detected': 'تم اكتشاف آفة مشتبهة',
    'A lesion was detected in the MRI image that may be associated with Multiple Sclerosis (MS) or another demyelinating condition.':
      'تم اكتشاف آفة في صورة الرنين قد تكون مرتبطة بالتصلب المتعدد (MS) أو بحالة أخرى مزيلة للميالين.',
    'Highest confidence among the lesion regions returned by the model.': 'أعلى نسبة ثقة بين مناطق الآفات التي حددها النموذج.',
    'Low-confidence finding': 'نتيجة منخفضة الثقة',
    'The model returned a possible lesion below the 70% review threshold. This result is inconclusive and should not be read as normal or abnormal without expert review.':
      'رصد النموذج آفة محتملة بثقة أقل من حد المراجعة 70%. هذه النتيجة غير حاسمة ولا ينبغي اعتبارها طبيعية أو غير طبيعية دون مراجعة مختص.',
    'Below the 70% threshold (marker on the bar) used to report a suspicious lesion.': 'أقل من حد 70% (العلامة على الشريط) المستخدم للإبلاغ عن آفة مشتبهة.',
    'No suspicious MS-related pattern detected': 'لم يُكتشف نمط مشتبه مرتبط بالتصلب المتعدد',
    'No suspicious MS-related pattern was detected by the current AI screening model.': 'لم يكتشف نموذج الفحص الحالي أي نمط مشتبه مرتبط بالتصلب المتعدد.',
    'The model returned no lesion regions, so no confidence score is reported.': 'لم يحدد النموذج أي مناطق آفات، لذلك لا توجد نسبة ثقة.',
    'Not applicable': 'غير منطبق',
    'Suspicious lesion': 'آفة مشتبهة',
    'Low confidence': 'ثقة منخفضة',
    'Clear': 'سليم',
    'No suspicious pattern': 'لا يوجد نمط مشتبه',
    'Upload rejected': 'رُفض الرفع',
    'Patient check': 'التحقق من المريض',
    'Analysis not completed': 'لم يكتمل التحليل',
    'Medical number conflict': 'تعارض في الرقم الطبي',
    'Missing information': 'معلومات ناقصة',
    'Analysis could not run': 'تعذّر تشغيل التحليل',
    'Duplicate MRI detected': 'تم اكتشاف صورة رنين مكررة',
    'Duplicate MRI — rejected': 'صورة رنين مكررة — مرفوضة',

    // ---------- scanner: next clinical step ----------
    'Next clinical step': 'الخطوة السريرية التالية',
    'Further clinical evaluation is recommended.': 'يوصى بمزيد من التقييم السريري.',
    'Expert radiology review of this MRI is recommended first.': 'يوصى أولاً بمراجعة هذه الصورة من أخصائي أشعة.',
    'Recommended diagnostic tests': 'الفحوصات التشخيصية الموصى بها',
    'If clinical suspicion of MS remains after review': 'إذا استمر الاشتباه السريري بالتصلب المتعدد بعد المراجعة',
    'Lumbar puncture': 'البزل القطني',
    'CSF analysis for oligoclonal bands (OCBs) and kappa free light chains (κ-FLC).':
      'تحليل السائل النخاعي للكشف عن الأشرطة قليلة النسيلة (OCBs) وسلاسل كابا الخفيفة الحرة (κ-FLC).',
    'Contrast-enhanced MRI — brain & spinal cord': 'رنين مغناطيسي بالصبغة — الدماغ والحبل الشوكي',
    'Gadolinium MRI to assess lesion spread in space and time (McDonald criteria).': 'رنين بصبغة الجادولينيوم لتقييم انتشار الآفات مكانياً وزمانياً (معايير ماكدونالد).',
    'Diagnostic tests only. This tool does not suggest any treatment.': 'فحوصات تشخيصية فقط. هذه الأداة لا تقترح أي علاج.',
    'Saved securely to the Patient Registry': 'حُفظ بأمان في سجل المرضى',

    // ---------- scanner: technology ----------
    'From MRI image to clinical insight': 'من صورة الرنين إلى رؤية سريرية',
    'A low-cost Raspberry Pi device that brings AI screening to clinics with limited access to MS specialists.':
      'جهاز Raspberry Pi منخفض التكلفة يوفّر الفحص بالذكاء الاصطناعي للعيادات التي تفتقر إلى أخصائيي التصلب المتعدد.',
    'Capture': 'الالتقاط',
    'Raspberry Pi Camera Module v2 or direct image upload.': 'كاميرا Raspberry Pi Module v2 أو رفع الصورة مباشرة.',
    'Detect': 'الكشف',
    'YOLO11n lesion detector on the grayscale MRI, with test-time augmentation, at 320 and 640 px.':
      'كاشف الآفات YOLO11n على صورة الرنين الرمادية، مع تعزيز وقت الاختبار، بحجمي 320 و640 بكسل.',
    'Focal check': 'فحص البؤر',
    'Regions too large to be a lesion (whole-brain boxes) are ignored, so only focal findings count.':
      'تُتجاهل المناطق الأكبر من أن تكون آفة (مربعات الدماغ كاملاً)، فلا تُحتسب إلا النتائج البؤرية.',
    'Report': 'التقرير',
    'Finding, confidence, flagged regions, and next clinical step — saved to the record.':
      'النتيجة، ونسبة الثقة، والمناطق المحددة، والخطوة السريرية التالية — تُحفظ في السجل.',
    'AI model': 'نموذج الذكاء الاصطناعي',
    "YOLO11n fine-tuned on labeled MRI slices (100 epochs, 640 px). Metrics are from the model's validation split.":
      'YOLO11n مُدرَّب على شرائح رنين موسومة (100 دورة تدريب، 640 بكسل). المقاييس من بيانات التحقق الخاصة بالنموذج.',
    'Validation metrics are not a clinical validation. Prospective evaluation on local clinical data is planned.':
      'مقاييس التحقق ليست تحققاً سريرياً. من المخطط إجراء تقييم مستقبلي على بيانات سريرية محلية.',
    'Device': 'الجهاز',
    'Raspberry Pi 5 (4 GB) with Camera Module v2 and touch display': 'Raspberry Pi 5 (4 جيجابايت) مع كاميرا Module v2 وشاشة لمس',
    'AI analysis runs locally on the device — MRI images are not uploaded to any cloud service':
      'يعمل تحليل الذكاء الاصطناعي محلياً على الجهاز — لا تُرفع صور الرنين إلى أي خدمة سحابية',
    'Low-cost, portable hardware suited to clinics and screening centers': 'عتاد منخفض التكلفة وقابل للنقل يناسب العيادات ومراكز الفحص',
    'Same software runs on a Windows workstation': 'البرنامج نفسه يعمل على حاسوب Windows',
    'Privacy & safety': 'الخصوصية والأمان',
    'Server accepts connections from this device only (localhost)': 'الخادم يقبل الاتصالات من هذا الجهاز فقط (localhost)',
    'Required patient identifiers; one medical number per patient': 'معرّفات المريض إلزامية؛ رقم طبي واحد لكل مريض',
    'Duplicate MRI protection via image fingerprints (SHA-256)': 'منع تكرار صور الرنين عبر بصمات الصور (SHA-256)',
    'CSRF protection, rate limiting, and an audit log of every action': 'حماية CSRF، وتحديد معدل الطلبات، وسجل تدقيق لكل إجراء',
    'Automatic daily database backups (last 7 kept)': 'نسخ احتياطي يومي تلقائي لقاعدة البيانات (يُحتفظ بآخر 7 نسخ)',
    'AI-assisted MS lesion screening · Technical Digital College for Girls, Riyadh': 'الكشف عن آفات التصلب المتعدد بمساعدة الذكاء الاصطناعي · الكلية التقنية الرقمية للبنات بالرياض',
    'Clinical decision-support prototype. Not a medical device. Final diagnosis requires clinical assessment and appropriate diagnostic criteria.':
      'نموذج أولي لدعم القرار السريري. ليس جهازاً طبياً. يتطلب التشخيص النهائي تقييماً سريرياً ومعايير تشخيصية مناسبة.',

    // ---------- scanner: messages ----------
    'Patient name is required.': 'اسم المريض مطلوب.',
    'Medical number is required.': 'الرقم الطبي مطلوب.',
    'Use letters, digits, - _ / . only (maximum 30 characters).': 'استخدم الحروف والأرقام و - _ / . فقط (30 حرفاً كحد أقصى).',
    'Medical number belongs to another patient.': 'الرقم الطبي مسجّل لمريض آخر.',
    'This browser cannot access the camera. Open the app at http://localhost.': 'هذا المتصفح لا يستطيع الوصول إلى الكاميرا. افتح التطبيق عبر http://localhost.',
    'Camera could not be started. Allow camera access in the browser, or use Upload.': 'تعذّر تشغيل الكاميرا. اسمح للمتصفح باستخدام الكاميرا، أو استخدم الرفع.',
    'Unsupported file type. Use PNG, JPG, WebP, or BMP.': 'نوع الملف غير مدعوم. استخدم PNG أو JPG أو WebP أو BMP.',
    'The image must be 10 MB or smaller.': 'يجب ألا يتجاوز حجم الصورة 10 ميجابايت.',
    'The image file could not be read.': 'تعذّرت قراءة ملف الصورة.',
    'Start the camera and capture the MRI image.': 'شغّل الكاميرا والتقط صورة الرنين.',
    'An MRI image is required.': 'صورة الرنين مطلوبة.',
    'The AI model is still loading. Please wait a moment.': 'النموذج لا يزال قيد التحميل. يرجى الانتظار قليلاً.',
    'Unexpected response from the server.': 'استجابة غير متوقعة من الخادم.',
    'Unexpected error.': 'خطأ غير متوقع.',
    'The local server is not responding. Please restart it.': 'الخادم المحلي لا يستجيب. يرجى إعادة تشغيله.',
    // server messages
    'Request not allowed.': 'الطلب غير مسموح.',
    'Too many requests. Please wait a minute and try again.': 'طلبات كثيرة. انتظر دقيقة ثم حاول مرة أخرى.',
    'Request could not be verified. Please reload the page.': 'تعذّر التحقق من الطلب. أعد تحميل الصفحة.',
    'Unsupported request type.': 'نوع الطلب غير مدعوم.',
    'Invalid request length.': 'طول الطلب غير صالح.',
    'No valid MRI image was received.': 'لم تصل صورة رنين صالحة.',
    'Invalid request data.': 'بيانات الطلب غير صالحة.',
    'Required patient information is missing.': 'بيانات المريض الإلزامية ناقصة.',
    'The AI model is still loading. Please wait a moment and try again.': 'النموذج لا يزال قيد التحميل. انتظر قليلاً ثم حاول مرة أخرى.',
    'The image file could not be read.': 'تعذّرت قراءة ملف الصورة.',
    'Image dimensions are not supported.': 'أبعاد الصورة غير مدعومة.',
    'This MRI image has already been associated with an existing patient record and cannot be uploaded again. The original patient record has not been changed.':
      'صورة الرنين هذه مرتبطة مسبقاً بسجل مريض آخر ولا يمكن رفعها مرة أخرى. لم يتم تغيير سجل المريض الأصلي.',
    'This medical number is already registered to a different patient name. Check the medical number or use the registered name.':
      'هذا الرقم الطبي مسجّل باسم مريض آخر. تحقق من الرقم الطبي أو استخدم الاسم المسجّل.',
    'The image could not be saved.': 'تعذّر حفظ الصورة.',
    'The image could not be analyzed.': 'تعذّر تحليل الصورة.',
    'The scan result could not be saved.': 'تعذّر حفظ نتيجة الفحص.',
    'Scan not found.': 'الفحص غير موجود.',

    // ---------- registry ----------
    'Patient Registry · MS SmartScan': 'سجل المرضى · MS SmartScan',
    'MS SmartScan Patient Registry': 'سجل مرضى MS SmartScan',
    'Sites': 'المواقع',
    'Patient Registry': 'سجل المرضى',
    'Open the MRI Scanner (separate site)': 'فتح موقع فحص الرنين (موقع مستقل)',
    'MRI Scanner': 'فحص الرنين',
    'Records are stored only on this device': 'السجلات محفوظة على هذا الجهاز فقط',
    'Receives new scans from the MRI Scanner automatically': 'يستقبل الفحوصات الجديدة من موقع الفحص تلقائياً',
    'Connecting…': 'جارٍ الاتصال…',
    'Reconnecting…': 'جارٍ إعادة الاتصال…',
    'Live · connected to Scanner': 'مباشر · متصل بموقع الفحص',
    'Live updates unavailable': 'التحديث المباشر غير متاح',
    'Connected to the MRI Scanner': 'متصل بموقع فحص الرنين',
    'Patient & Scan Registry': 'سجل المرضى والفحوصات',
    'Every analysis from the MRI Scanner lands here automatically: patient, medical number, AI finding, confidence, and images. No refresh needed.':
      'كل تحليل من موقع الفحص يصل إلى هنا تلقائياً: المريض، والرقم الطبي، ونتيجة الذكاء الاصطناعي، ونسبة الثقة، والصور. دون الحاجة إلى تحديث الصفحة.',
    'New scan in MRI Scanner': 'فحص جديد في موقع الفحص',
    'Loading records…': 'جارٍ تحميل السجلات…',
    'Overview': 'نظرة عامة',
    'Screening summary': 'ملخص الفحوصات',
    'Totals, recent activity, and every scan with its AI finding. Click a row for the full scan.':
      'الإجماليات، والنشاط الأخير، وكل فحص مع نتيجته. انقر على أي صف لعرض الفحص كاملاً.',
    'Download the records shown below as a formatted Excel workbook': 'تنزيل السجلات المعروضة أدناه كملف Excel منسّق',
    'Export to Excel': 'تصدير إلى Excel',
    'Total scans': 'إجمالي الفحوصات',
    'Patients': 'المرضى',
    'Screening activity': 'نشاط الفحص',
    'Last 14 days': 'آخر 14 يوماً',
    'Scans per day, last 14 days': 'الفحوصات يومياً، آخر 14 يوماً',
    'Scans': 'الفحوصات',
    'Suspicious': 'مشتبه',
    'Search by patient name or medical number': 'ابحث باسم المريض أو الرقم الطبي',
    'Search records': 'البحث في السجلات',
    'Filter by finding': 'تصفية حسب النتيجة',
    'All': 'الكل',
    'Date & time': 'التاريخ والوقت',
    'Confidence': 'الثقة',
    'Regions': 'المناطق',
    'Actions': 'إجراءات',
    'View': 'عرض',
    'No scans recorded yet': 'لا توجد فحوصات مسجلة بعد',
    "Completed analyses will appear here with the patient's details.": 'ستظهر التحليلات المكتملة هنا مع بيانات المريض.',
    'Scans completed in the MRI Scanner appear here automatically.': 'تظهر الفحوصات المكتملة في موقع الفحص هنا تلقائياً.',
    'No matching records': 'لا توجد سجلات مطابقة',
    'Try a different name, medical number, or filter.': 'جرّب اسماً أو رقماً طبياً أو تصفية مختلفة.',
    'Patient Registry · AI-assisted MS lesion screening · Technical Digital College for Girls, Riyadh':
      'سجل المرضى · الكشف عن آفات التصلب المتعدد بمساعدة الذكاء الاصطناعي · الكلية التقنية الرقمية للبنات بالرياض',
    'Close': 'إغلاق',
    'MRI scan': 'صورة الرنين',
    'Scan date': 'تاريخ الفحص',
    'Scan ID': 'رقم الفحص',
    'Model': 'النموذج',
    'Legacy': 'قديم',
    'Delete scan': 'حذف الفحص',
    'Unnamed (legacy record)': 'بدون اسم (سجل قديم)',
    'Legacy scan': 'فحص قديم',
    'No medical number': 'بدون رقم طبي',
    'No records to export.': 'لا توجد سجلات للتصدير.',
    'The scan could not be deleted. Reload the page and try again.': 'تعذّر حذف الفحص. أعد تحميل الصفحة وحاول مرة أخرى.',
    'Scan deleted.': 'تم حذف الفحص.',
    'Suspicious lesion detected that may be associated with MS or another demyelinating condition. Recommended diagnostic tests: lumbar puncture (CSF: OCBs, κ-FLC) and contrast-enhanced MRI of the brain and spinal cord.':
      'تم اكتشاف آفة مشتبهة قد تكون مرتبطة بالتصلب المتعدد أو بحالة أخرى مزيلة للميالين. الفحوصات التشخيصية الموصى بها: البزل القطني (السائل النخاعي: OCBs و κ-FLC) ورنين مغناطيسي بالصبغة للدماغ والحبل الشوكي.',
    'Low-confidence finding below the 70% review threshold. Expert radiology review is recommended first; if MS is still suspected, consider lumbar puncture and contrast-enhanced MRI.':
      'نتيجة منخفضة الثقة أقل من حد المراجعة 70%. يوصى أولاً بمراجعة أخصائي أشعة؛ وإذا استمر الاشتباه بالتصلب المتعدد، يُنظر في البزل القطني والرنين المغناطيسي بالصبغة.',
    's': 'ث',
  };

  const MONTHS = { Jan: 'يناير', Feb: 'فبراير', Mar: 'مارس', Apr: 'أبريل', May: 'مايو', Jun: 'يونيو', Jul: 'يوليو', Aug: 'أغسطس', Sep: 'سبتمبر', Sept: 'سبتمبر', Oct: 'أكتوبر', Nov: 'نوفمبر', Dec: 'ديسمبر' };
  const DATE_RE = /\b(\d{1,2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec) (\d{4})(?:, (\d{2}:\d{2}))?/g;
  const arDate = (s) => s.replace(DATE_RE, (_, d, m, y, t) => `${d} ${MONTHS[m]} ${y}${t ? '، ' + t : ''}`);

  // Texts that contain numbers or names
  const PATTERNS = [
    [/^Complete · ([\d.]+)s$/, (m) => `مكتمل · ${m[1]} ث`],
    [/^([\d.]+) s$/, (m) => `${m[1]} ث`],
    [/^([\d.]+) seconds?$/, (m) => `${m[1]} ث`],
    [/^Updated (.+)$/, (m) => `آخر تحديث ${m[1]}`],
    [/^Exporting (\d+) records? to Excel…$/, (m) => `جارٍ تصدير ${m[1]} سجل إلى Excel…`],
    [/^New scan received: (.+) · (.+)$/, (m) => `فحص جديد: ${m[1] === 'Patient' ? 'مريض' : m[1]} · ${AR[m[2]] || m[2]}`],
    [/^Delete this scan for (.+)\? This cannot be undone\.$/, (m) => `حذف فحص ${m[1] === 'this patient' ? 'هذا المريض' : m[1]}؟ لا يمكن التراجع عن هذا.`],
    [/^Medical no\. (.+)$/, (m) => `الرقم الطبي ${m[1]}`],
    [/^Camera (\d+)$/, (m) => `كاميرا ${m[1]}`],
    [/^(\d+) × (\d+) px(?: · ([\d.]+) MB)?$/, (m) => `${m[1]} × ${m[2]} بكسل${m[3] ? ` · ${m[3]} ميجابايت` : ''}`],
    [/^(\d{4}-\d{2}-\d{2}): (\d+) scan\(s\), (\d+) suspicious$/, (m) => `${m[1]}: ${m[2]} فحص، ${m[3]} مشتبه`],
  ];

  function translate(text) {
    const core = text.replace(/\s+/g, ' ').trim();
    if (!core) return null;
    let out = AR[core];
    if (out === undefined) {
      for (const [re, fn] of PATTERNS) { const m = core.match(re); if (m) { out = fn(m); break; } }
    }
    if (out === undefined) { const d = arDate(core); if (d !== core) out = d; }
    if (out === undefined) return null;
    const lead = text.match(/^\s*/)[0], trail = text.match(/\s*$/)[0];
    return lead + out + trail;
  }

  // ---------- applying to the page ----------
  const ATTRS = ['placeholder', 'title', 'aria-label', 'alt'];
  const english = new WeakMap();   // text node -> original English
  const arabic = new WeakMap();    // text node -> the Arabic we wrote
  let lang = 'en';
  try { lang = localStorage.getItem('mss-lang') === 'ar' ? 'ar' : 'en'; } catch (e) { /* storage blocked */ }

  const skip = (el) => !el || el.closest('script, style, input, textarea, select, [data-no-i18n], .mrn, .mono');

  function textNode(node) {
    if (skip(node.parentElement)) return;
    if (lang === 'ar') {
      if (arabic.get(node) === node.nodeValue) return;            // already ours
      const tr = translate(node.nodeValue);
      if (tr === null) return;
      english.set(node, node.nodeValue); arabic.set(node, tr); node.nodeValue = tr;
    } else if (english.has(node) && arabic.get(node) === node.nodeValue) {
      node.nodeValue = english.get(node); arabic.delete(node);
    }
  }

  function element(el) {
    if (el.closest('[data-no-i18n]')) return;
    for (const a of ATTRS) {
      if (!el.hasAttribute(a)) continue;
      const cur = el.getAttribute(a), keyEn = 'data-en-' + a, keyAr = 'data-ar-' + a;
      if (lang === 'ar') {
        if (el.getAttribute(keyAr) === cur) continue;
        const tr = translate(cur);
        if (tr === null) continue;
        el.setAttribute(keyEn, cur); el.setAttribute(keyAr, tr); el.setAttribute(a, tr);
      } else if (el.hasAttribute(keyEn) && el.getAttribute(keyAr) === cur) {
        el.setAttribute(a, el.getAttribute(keyEn)); el.removeAttribute(keyAr);
      }
    }
  }

  function walk(root) {
    if (root.nodeType === 3) return textNode(root);
    if (root.nodeType !== 1) return;
    element(root);
    const tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    let n; while ((n = tw.nextNode())) n.nodeType === 3 ? textNode(n) : element(n);
  }

  let titleEn = document.title;
  function apply() {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
    if (lang === 'ar') { titleEn = document.title; document.title = translate(document.title) || document.title; }
    else document.title = titleEn;
    walk(document.body);
    const btn = document.getElementById('langBtn');
    if (btn) { btn.querySelector('span').textContent = lang === 'ar' ? 'English' : 'العربية'; btn.setAttribute('lang', lang === 'ar' ? 'en' : 'ar'); }
  }

  // Texts the page scripts add later (results, messages, records) are translated as they appear
  new MutationObserver((list) => {
    if (lang !== 'ar') return;
    for (const m of list) {
      if (m.type === 'characterData') textNode(m.target);
      else if (m.type === 'attributes') element(m.target);
      else m.addedNodes.forEach(walk);
    }
  }).observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS });

  // Confirmation dialogs
  const nativeConfirm = window.confirm.bind(window);
  window.confirm = (msg) => nativeConfirm(lang === 'ar' ? (translate(String(msg)) || msg) : msg);

  document.getElementById('langBtn')?.addEventListener('click', () => {
    lang = lang === 'ar' ? 'en' : 'ar';
    try { localStorage.setItem('mss-lang', lang); } catch (e) { /* ignore */ }
    apply();
  });

  apply();
  window.MSS_I18N = { translate, get lang() { return lang; } };
})();
