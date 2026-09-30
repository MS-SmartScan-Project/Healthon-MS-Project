@echo off
setlocal
title MS SmartScan
cd /d "%~dp0"

set "PYTHON_EXE="
if exist "%LocalAppData%\Programs\Python\Python314\python.exe" set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python314\python.exe"
if not defined PYTHON_EXE if exist "%LocalAppData%\Programs\Python\Python313\python.exe" set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python313\python.exe"
if not defined PYTHON_EXE if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python312\python.exe"

if not defined PYTHON_EXE (
  py -3 -c "import sys" >nul 2>nul
  if not errorlevel 1 set "PYTHON_EXE=py -3"
)

if not defined PYTHON_EXE (
  python -c "import sys" >nul 2>nul
  if not errorlevel 1 set "PYTHON_EXE=python"
)

if not defined PYTHON_EXE goto missing_python
%PYTHON_EXE% -c "import cv2, ultralytics" >nul 2>nul
if errorlevel 1 goto missing_packages
%PYTHON_EXE% server.py
goto end

:missing_packages
echo.
echo Required packages are missing.
echo Run: %PYTHON_EXE% -m pip install -r requirements.txt
goto end

:missing_python
echo.
echo Python 3.12 or newer was not found.
echo Install Python, then run this file again.

:end
pause
endlocal
