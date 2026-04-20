@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0\.."

set PYTHON_VERSION=3.14.4
set PYTHON=.venv\Scripts\python.exe

echo ========================================
echo   automator - initial setup
echo ========================================
echo   project root  : %cd%
echo   Python        : %PYTHON_VERSION%
echo.

REM ── 0. uv check / install ──────────────────────────────────────
where uv >nul 2>&1
if errorlevel 1 (
    echo   [0/5] Installing uv...
    powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
    if errorlevel 1 goto :fail
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
    echo         done
) else (
    echo   [0/5] uv found
)

REM ── 1. Python 3.14 ─────────────────────────────────────────────
echo   [1/5] Ensuring CPython %PYTHON_VERSION%...
uv python install %PYTHON_VERSION%
if errorlevel 1 goto :fail
echo         done

REM ── 2. venv ────────────────────────────────────────────────────
if exist .venv (
    echo   [2/5] .venv exists - will reuse if version matches
    %PYTHON% --version 2>nul | findstr "%PYTHON_VERSION%" >nul
    if errorlevel 1 (
        echo         version mismatch - recreating
        rmdir /s /q .venv
        uv venv --python %PYTHON_VERSION% .venv
        if errorlevel 1 goto :fail
    )
) else (
    echo   [2/5] Creating venv...
    uv venv --python %PYTHON_VERSION% .venv
    if errorlevel 1 goto :fail
)
echo         done

REM ── 3. packages ────────────────────────────────────────────────
echo   [3/5] Installing packages...
uv pip install --python %PYTHON% -r requirements.txt
if errorlevel 1 goto :fail
echo         done

REM ── 4. Playwright Chromium ─────────────────────────────────────
echo   [4/5] Installing Playwright Chromium...
%PYTHON% -m playwright install chromium
if errorlevel 1 (
    echo         retrying with deps...
    %PYTHON% -m playwright install --with-deps chromium
    if errorlevel 1 goto :fail
)
echo         done

REM ── 5. directories ─────────────────────────────────────────────
echo   [5/5] Creating directories...
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
