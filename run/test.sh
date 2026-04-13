#!/usr/bin/env bash
# run/test.sh — 테스트 실행
#
# 자동 마킹: conftest.py가 디렉토리 기반으로 마커를 붙입니다.
#   tests/unit/          → @pytest.mark.unit
#   tests/integration/   → @pytest.mark.integration
#   tests/browser/       → @pytest.mark.browser
#   tests/e2e/           → @pytest.mark.e2e
#
# 사용법:
#   bash ./run/test.sh                 # unit + integration + browser (기본)
#   bash ./run/test.sh --unit          # unit 만
#   bash ./run/test.sh --cli           # unit/cli 만
#   bash ./run/test.sh --browser       # browser 만
#   bash ./run/test.sh --e2e           # unit + integration + browser + e2e
#   bash ./run/test.sh --all           # everything
#   bash ./run/test.sh --session       # 네이버 세션 준비 (자동 로그인)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

cd "${PROJECT_ROOT}"

# ── .env 로드 ────────────────────────────────────────────────────────────────
if [ -f "${PROJECT_ROOT}/.env" ]; then
    set -o allexport
    source "${PROJECT_ROOT}/.env"
    set +o allexport
fi

# ── venv 확인 ─────────────────────────────────────────────────────────────────
if [ -d "${VENV_DIR}" ]; then
    source "${VENV_DIR}/bin/activate"
fi

# ── 모드 선택 ─────────────────────────────────────────────────────────────────

MODE="${1:---default}"

case "${MODE}" in

  --default)
    echo "── unit/automator ────────────────────────"
    pytest tests/unit/automator/ -v
    echo ""
    echo "── unit/cli ────────────────────────────"
    pytest tests/unit/cli/ -v
    echo ""
    echo "── integration/automator ────────────────"
    pytest tests/integration/automator/ -v
    echo ""
    echo "── browser ──────────────────────────────"
    pytest tests/browser/ -v
    ;;

  --unit)
    echo "── unit/automator ────────────────────────"
    pytest tests/unit/automator/ -v
    echo ""
    echo "── unit/cli ────────────────────────────"
    pytest tests/unit/cli/ -v
    ;;

  --cli)
    echo "── unit/cli ────────────────────────────"
    pytest tests/unit/cli/ -v
    ;;

  --browser)
    echo "── browser ──────────────────────────────"
    pytest tests/browser/ -v
    ;;

  --e2e)
    echo "── [1/2] unit + integration + browser ────"
    pytest tests/unit/ tests/integration/automator/ tests/browser/ -v
    echo ""
    echo "── [2/2] e2e ──────────────────────────────"
    pytest tests/e2e/ -v
    ;;

  --all)
    echo "── [1/2] unit + integration + browser ────"
    pytest tests/unit/ tests/integration/automator/ tests/browser/ -v
    echo ""
    echo "── [2/2] e2e ──────────────────────────────"
    pytest tests/e2e/ -v
    ;;

  --session)
    echo "  네이버 세션 준비 (자동 로그인)"
    echo "  CAPTCHA/2차 인증이 뜨면 직접 처리하세요."
    echo ""
    python3 -c "
import os, random
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from automator.selector_loader import SelectorLoader

load_dotenv()
naver_id  = os.getenv('NAVER_ID', '')
naver_pw  = os.getenv('NAVER_PW', '')
blog_id   = os.getenv('NAVER_BLOG_ID', naver_id)
out_path  = os.getenv('SESSION_PATH', 'session_state.json')

if not naver_id or not naver_pw:
    print('  .env에 NAVER_ID, NAVER_PW를 설정하세요.')
    exit(1)

sel = SelectorLoader.load('selectors/naver/login.yaml')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx  = browser.new_context(locale='ko-KR', timezone_id='Asia/Seoul')
    page = ctx.new_page()
    page.goto('https://nid.naver.com/nidlogin.login', wait_until='domcontentloaded')

    # CLI auto_login과 동일한 human-like 타이핑
    id_field = sel.locator(page, 'naver_login_id')
    id_field.wait_for(state='visible', timeout=10_000)
    id_field.click()
    id_field.press_sequentially(naver_id, delay=random.randint(80, 180))

    page.keyboard.press('Tab')
    page.wait_for_timeout(random.randint(150, 350))

    pw_field = sel.locator(page, 'naver_login_pw')
    pw_field.wait_for(state='visible', timeout=5_000)
    pw_field.press_sequentially(naver_pw, delay=random.randint(80, 180))

    page.wait_for_timeout(random.randint(300, 700))
    sel.locator(page, 'naver_login_submit').click()

    print('  로그인 중... CAPTCHA/2차 인증이 뜨면 직접 처리하세요.')
    page.wait_for_url(
        lambda url: 'nidlogin' not in url and 'naver.com' in url,
        timeout=300_000,
    )

    # 세션 유효성 확인
    page.goto(
        f'https://blog.naver.com/{blog_id}?Redirect=Write&',
        wait_until='domcontentloaded',
        timeout=15_000,
    )
    if 'nidlogin' in page.url:
        print('  세션 검증 실패 — 로그인 상태가 아닙니다.')
        browser.close()
        exit(1)

    ctx.storage_state(path=out_path)
    browser.close()

print(f'  세션 저장 완료: {out_path}')
"
    ;;

  --help|-h)
    cat << 'HELP'

  bash ./run/test.sh                 # unit + integration + browser (기본)
  bash ./run/test.sh --unit          # unit 만
  bash ./run/test.sh --cli           # unit/cli 만
  bash ./run/test.sh --browser       # browser 만
  bash ./run/test.sh --e2e           # unit + integration + browser + e2e
  bash ./run/test.sh --all           # everything
  bash ./run/test.sh --session       # 네이버 세션 준비 (자동 로그인)

  ── tests/unit/automator/            Automator 순수 단위 테스트
      test_title_generator.py         generate_title + validate_template
      test_paragraph_generator.py     generate_paragraph stubs
      test_ai_section.py              AI section rendering
      test_layout.py                  Section/Block validation
      test_post_step.py               PostStep.execute dispatch
      test_image_processor.py         process_image (ImageBlock + FeaturedImageBlock)
      test_exif_optimizer.py          EXIF metadata handling
      test_ports.py                   Port ABCs + test doubles
      test_block_factory.py           block_type → Block + media_id resolution
      test_preset_loader.py           JSON config → frozen dataclass
      test_markdown_parser.py         Markdown parsing
      test_naver_checker.py           Naver title duplicate checker
      test_post_preview.py            Post preview rendering
      test_region.py                  Screen region coordinates
      test_region_effect.py           Visual effects on regions
      test_title_check.py             Title check logic

  ── tests/unit/cli/                  CLI 단위 테스트
      test_campaign_executor.py       CampaignExecutor
      test_combo_builder.py           Combo generation
      test_config_loader.py           YAML/JSON config loading
      test_dsl.py                     DSL interpolation
      test_main_flags.py              CLI argument parsing
      test_map_loader.py              Map file loading
      test_schedule.py                Schedule parsing
      test_session_store.py           Session persistence (file/Redis)
      test_spec_builder.py            Spec building from combos

  ── tests/integration/automator/     Automator 통합 테스트
      test_spec_builder.py            PostingSpec immutability
      test_spec_validator.py          SpecValidator rules
      test_content_builder.py         ContentBuilder block → step
      test_runner.py                  JobRunner editor call sequence
      test_publish_option.py          Schedule resolution

  ── tests/browser/                   Playwright mocks (no real browser)
      test_smart_editor.py            SmartEditorOne DOM wiring
      test_browser_actions.py         Pure DOM functions
      test_browser_config.py          BrowserSettings
      test_browser_selectors.py       SelectorLoader

  ── tests/e2e/                       Real browser (requires session)
      test_e2e_naver.py               E2E smoke

HELP
    ;;

  *)
    echo "알 수 없는 옵션: ${MODE}  (--help 로 도움말 확인)"
    exit 1
    ;;

esac

echo ""
echo "완료"
