@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0\.."

set PYTHON=.venv\Scripts\python.exe

REM ── venv 확인 ──
if not exist %PYTHON% (
    echo.
    echo   [ERROR] .venv이 없습니다. 먼저 init.bat을 실행하세요.
    echo           run\init.bat
    echo.
    goto :end
)

REM ── Playwright 브라우저 확인 ──
%PYTHON% -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(headless=True); b.close(); p.stop()" >nul 2>&1
if errorlevel 1 (
    echo   [INFO] Playwright Chromium 설치 중...
    %PYTHON% -m playwright install chromium
    if errorlevel 1 (
        echo.
        echo   [ERROR] Playwright 설치 실패. init.bat을 다시 실행하세요.
        goto :end
    )
    echo         done
    echo.
)

REM ── GUI 실행 ──
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
