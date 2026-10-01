@echo off
setlocal
title MS SmartScan - Patient Registry
cd /d "%~dp0"
rem Starts only the Patient Registry website (http://localhost:8001) and opens it in the browser.
rem Needs Python only - no AI libraries.

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

%PYTHON_EXE% server.py --open
goto end

:missing_python
echo.
echo Python 3.12 or newer was not found.
echo Install Python, then run this file again.

:end
pause
endlocal
