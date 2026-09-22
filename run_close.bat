@echo off
REM Windows 작업 스케줄러 등록용 실행 스크립트 (장마감 브리핑)
cd /d "%~dp0"
call venv\Scripts\activate.bat
python -m src.main --mode close
