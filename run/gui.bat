@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0\.."
.venv\Scripts\python -m gui
if errorlevel 1 (
    echo.
    echo [ERROR] GUI failed to start. See above for details.
    echo.
    pause
)
