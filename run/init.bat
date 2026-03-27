@echo off
REM run\init.bat — 처음 한 번만 실행 (Windows)
cd /d "%~dp0\.."

echo ========================================
echo   automator — 초기 환경 설정
echo ========================================
echo   프로젝트 루트 : %cd%
echo.

REM 1. 가상환경
if exist .venv (
    echo   [1/4] .venv 이미 존재 — 건너뜀
) else (
    echo   [1/4] 가상환경 생성 중...
    python -m venv .venv
    echo         완료
)

REM 2. 활성화
call .venv\Scripts\activate.bat

REM 3. 패키지 설치
echo   [2/4] 패키지 설치 중...
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo         완료

REM 4. Playwright Chromium
echo   [3/4] Playwright Chromium 설치 중...
playwright install chromium
echo         완료

REM 5. 로그 디렉토리
if not exist logs mkdir logs

echo.
echo ========================================
echo   설정 완료
echo ========================================
echo.
echo   다음 단계:
echo     copy .env.example .env            # 환경 파일 설정
echo     run\gui.bat                       # 캠페인 빌더 GUI 실행
echo     run\test.bat                      # 테스트 (선택)
echo.
pause
