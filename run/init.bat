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
    echo         done
)

call .venv\Scripts\activate.bat

echo   [2/3] installing packages...
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo         done

echo   [3/3] installing Playwright Chromium...
playwright install chromium
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
pause
