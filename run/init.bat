@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0\.."

echo ========================================
echo   automator - initial setup
echo ========================================
echo   project root : %cd%
echo.

if exist .venv (
    echo   [1/3] .venv exists - skip
) else (
    echo   [1/3] creating venv...
    python -m venv .venv
    if errorlevel 1 goto :fail
    echo         done
)

call .venv\Scripts\activate.bat
if errorlevel 1 goto :fail

echo   [2/3] installing packages...
python -m pip install --quiet --upgrade pip
if errorlevel 1 goto :fail
python -m pip install --quiet -r requirements.txt
if errorlevel 1 goto :fail
echo         done

echo   [3/3] installing Playwright Chromium...
python -m playwright install chromium
if errorlevel 1 goto :fail
echo         done

if not exist logs mkdir logs

echo.
echo ========================================
echo   setup complete
echo ========================================
echo.
echo   next:
echo     copy .env.example .env
echo     run\gui.bat
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
