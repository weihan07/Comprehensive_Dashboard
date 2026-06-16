@echo off
title Sales Dashboard Launcher
echo ==========================================
echo    Global Recharge Sales Dashboard
echo ==========================================
echo.
cd /d "C:\Disk\LiuLian Tech Sdn. Bhd\Code\Sales Dashboard"

rem If server is already up, just open the browser
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo Dashboard server already running. Opening browser...
    start "" "http://127.0.0.1:8000"
    timeout /t 2 /nobreak >nul
    exit /b 0
)

echo Starting dashboard server...
start "Sales Dashboard Server" /min "sales_env\Scripts\python.exe" sales_dashboard.py

echo Loading data (this can take up to 2 minutes for large Excel files)...
echo Polling port 8000 for the server to come up...

set /a tries=0
:waitloop
timeout /t 3 /nobreak >nul
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 goto ready
set /a tries+=1
if %tries% geq 60 goto failed
echo   ... still waiting (%tries% / 60)
goto waitloop

:ready
echo Server is ready. Opening dashboard in your default browser...
start "" "http://127.0.0.1:8000"
timeout /t 2 /nobreak >nul
exit /b 0

:failed
echo.
echo ERROR: Dashboard server did not start within 3 minutes.
echo Check the minimized "Sales Dashboard Server" window for errors,
echo or run the script manually:
echo   cd "C:\Disk\LiuLian Tech Sdn. Bhd\Code\Sales Dashboard"
echo   sales_env\Scripts\python.exe sales_dashboard.py
echo.
pause
exit /b 1
