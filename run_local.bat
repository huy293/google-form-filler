@echo off
title Google Form Auto-Filler (Local Runner)
echo =========================================================
echo   KHOI CHAY GOOGLE FORM AUTO-FILLER TREN MAY TINH LOCAL
echo =========================================================
echo.
echo * Buoc 1: Tu dong giai phong cong 8888 (tat cac server cu)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8888') do taskkill /f /pid %%a 2>nul
echo.
echo * Buoc 2: Kiem tra va tu dong cai dat Chrome ao neu thieu...
python -m playwright install chromium
echo.
echo * Buoc 3: Khoi chay Server...
echo * Cua so trinh duyet Chrome se TU DONG BAT LEN tren may tinh 
echo   khi ban bam nut Dang ky.
echo.
echo * He thong se tu dong mo trang web http://localhost:8888
echo.
echo =========================================================
echo.

:: Open the browser after 2 seconds to let FastAPI boot up
start "" "http://localhost:8888"

:: Run server
python main.py

pause
