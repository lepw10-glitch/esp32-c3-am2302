@echo off
cd /d "%~dp0"
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:5000"
venv\Scripts\python.exe dashboard.py
pause