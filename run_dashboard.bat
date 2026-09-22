@echo off
REM 설정 대시보드 실행 (http://127.0.0.1:5050)
cd /d "%~dp0"
call venv\Scripts\activate.bat
python -m src.dashboard
