@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0\.."

set PYTHON=.venv\Scripts\python.exe

if not exist %PYTHON% (
    echo.
    echo   [ERROR] .venv not found. Run init.bat first.
    echo           run\init.bat
    echo.
    goto :end
)

%PYTHON% -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(headless=True); b.close(); p.stop()" >nul 2>&1
if errorlevel 1 (
    echo   [INFO] Installing Playwright Chromium...
    %PYTHON% -m playwright install chromium
    if errorlevel 1 (
        echo.
        echo   [ERROR] Playwright install failed. Run init.bat again.
        goto :end
    )
    echo         done
    echo.
)

%PYTHON% -m gui

if errorlevel 1 (
    echo.
    echo ========================================
    echo   [ERROR] GUI failed - see above
    echo ========================================
    echo.
)

:end
pause
