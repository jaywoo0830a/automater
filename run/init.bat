@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0\.."

set PYTHON=.venv\Scripts\python.exe

echo ========================================
echo   automator - initial setup
echo ========================================
echo   project root : %cd%
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] Python not found.
    echo           Install from https://www.python.org/downloads/
    goto :fail
)

if exist .venv (
    echo   [1/4] .venv exists - skip
) else (
    echo   [1/4] creating venv...
    python -m venv .venv
    if errorlevel 1 goto :fail
    echo         done
)

echo   [2/4] installing packages...
%PYTHON% -m pip install --upgrade pip -q
if errorlevel 1 goto :fail
%PYTHON% -m pip install -r requirements.txt -q
if errorlevel 1 goto :fail
echo         done

echo   [3/4] installing Playwright Chromium...
%PYTHON% -m playwright install chromium
if errorlevel 1 (
    echo         retrying with deps...
    %PYTHON% -m playwright install --with-deps chromium
    if errorlevel 1 goto :fail
)
echo         done

echo   [4/4] creating directories...
if not exist logs mkdir logs
if not exist sessions mkdir sessions
if not exist assets mkdir assets
if not exist assets\images mkdir assets\images
if not exist assets\thumbnails mkdir assets\thumbnails
if not exist assets\fonts mkdir assets\fonts
echo         done

if not exist .env (
    if exist .env.example (
        copy .env.example .env >nul
        echo.
        echo   [INFO] .env created. Please edit it.
    )
)

echo.
echo ========================================
echo   setup complete
echo ========================================
echo.
echo   next:
echo     1. Edit .env
echo     2. run\gui.bat
echo.
goto :end

:fail
echo.
echo ========================================
echo   [ERROR] setup failed - see above
echo ========================================
echo.

:end
pause
