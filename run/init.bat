@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0\.."

set PYTHON=.venv\Scripts\python.exe

echo ========================================
echo   automator - initial setup
echo ========================================
echo   project root : %cd%
echo.

REM ── Python 확인 ──
python --version >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] Python이 설치되어 있지 않습니다.
    echo           https://www.python.org/downloads/ 에서 설치하세요.
    goto :fail
)

REM ── 1. venv ──
if exist .venv (
    echo   [1/4] .venv exists - skip
) else (
    echo   [1/4] creating venv...
    python -m venv .venv
    if errorlevel 1 goto :fail
    echo         done
)

REM ── 2. pip + packages ──
echo   [2/4] installing packages...
%PYTHON% -m pip install --upgrade pip -q
if errorlevel 1 goto :fail
%PYTHON% -m pip install -r requirements.txt -q
if errorlevel 1 goto :fail
echo         done

REM ── 3. Playwright ──
echo   [3/4] installing Playwright Chromium...
%PYTHON% -m playwright install chromium
if errorlevel 1 (
    echo         [WARN] playwright install failed - retrying with deps...
    %PYTHON% -m playwright install --with-deps chromium
    if errorlevel 1 goto :fail
)
echo         done

REM ── 4. 디렉터리 생성 ──
echo   [4/4] creating directories...
if not exist logs mkdir logs
if not exist sessions mkdir sessions
if not exist assets\images mkdir assets\images
if not exist assets\thumbnails mkdir assets\thumbnails
if not exist assets\fonts mkdir assets\fonts
echo         done

REM ── .env 생성 ──
if not exist .env (
    if exist .env.example (
        copy .env.example .env >nul
        echo.
        echo   [INFO] .env 파일이 생성되었습니다. 편집해주세요.
    )
)

echo.
echo ========================================
echo   setup complete
echo ========================================
echo.
echo   next:
echo     1. .env 파일을 편집하세요 (NAVER_ID, NAVER_PW 등)
echo     2. run\gui.bat 로 GUI를 실행하세요
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
