@echo off
echo ====================================
echo Downloading Plotly.js on Windows PC
echo ====================================
echo.

REM Create directory if it doesn't exist
if not exist "web\static\js" mkdir web\static\js

echo Downloading Plotly.js from CDN...
echo This may take a minute (~3.5 MB)...
echo.

REM Download using PowerShell
powershell -Command "& {Invoke-WebRequest -Uri 'https://cdn.plotly.ly/plotly-2.27.0.min.js' -OutFile 'web\static\js\plotly-2.27.0.min.js'}"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo SUCCESS! Plotly.js downloaded
    echo ========================================
    echo.
    echo File location: web\static\js\plotly-2.27.0.min.js
    echo.
    echo Next steps:
    echo 1. Commit and push this file to GitHub:
    echo    git add web/static/js/plotly-2.27.0.min.js
    echo    git commit -m "Add Plotly.js for local hosting"
    echo    git push
    echo.
    echo 2. On the Pi, pull the changes:
    echo    git pull
    echo.
    echo 3. Restart web server on Pi:
    echo    python3 run_web_interface.py
    echo.
    echo 4. Refresh browser (Ctrl+Shift+R)
    echo.
    pause
) else (
    echo.
    echo ========================================
    echo ERROR: Download failed
    echo ========================================
    echo.
    echo Try manually:
    echo 1. Open: https://cdn.plotly.ly/plotly-2.27.0.min.js
    echo 2. Save as: web\static\js\plotly-2.27.0.min.js
    echo.
    pause
)
