#!/bin/bash
# MS SmartScan — تشغيل الموقعين على Raspberry Pi
#   Patient Registry: http://localhost:8001  (يعمل في الخلفية — افتحيه بنفسك في المتصفح)
#   MRI Scanner:      http://localhost:8000  (يفتح المتصفح تلقائياً)
cd "$(dirname "$0")"
[ -f .venv/bin/activate ] && source .venv/bin/activate
PY=$(command -v python || command -v python3)
export YOLO_OFFLINE=1   # the AI runs fully offline: no update or connectivity checks

"$PY" Patient-Registry/server.py &
REGISTRY_PID=$!
trap 'kill $REGISTRY_PID 2>/dev/null' EXIT   # إيقاف موقع السجل عند إغلاق موقع الفحص

"$PY" MRI-Scanner/server.py
