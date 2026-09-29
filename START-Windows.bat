@echo off
title MS SmartScan
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 ( py server.py & goto end )
where python >nul 2>nul
if %errorlevel%==0 ( python server.py & goto end )
echo.
echo  Python is not installed.
echo  Install it, tick "Add python.exe to PATH", then double-click this file again.
start "" https://www.python.org/downloads/
:end
pause
