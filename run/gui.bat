@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0\.."

.venv\Scripts\python -m gui

if errorlevel 1 (
    echo.
    echo ========================================
    echo   [ERROR] GUI failed - see above
    echo ========================================
    echo.
)

pause
