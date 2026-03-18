#!/usr/bin/env bash
# run/test.sh — 테스트 실행
#
# 파일 구조
# ----------
#   tests/
#     test_job_builder.py      PostingJob 빌더 불변성
#     test_job_validation.py   PostingJob.validate() 규칙
#     test_job_execution.py    PostingJob.run() 에디터 호출 순서
#     test_job_with_seo.py     SEOOption 연동
#     test_job_with_media.py   MediaOption 연동
#     test_editor_smart.py     SmartEditorOne DOM 조작
#     test_options_title.py    TitleOption + TitleGenerator
#     test_options_blocks.py   Block 유효성 검사
#     test_options_seo.py      SEOOption 검증
#     test_options_publish.py  PublishOption 검증 + 스케줄 해석
#     test_generator_paragraph.py  ParagraphGenerator
#     test_generator_image.py      ImageProcessor
#     test_generator_assets.py     AssetLoader
#     test_browser_actions.py      Playwright 순수 함수
#     test_browser_selectors.py    SelectorLoader
#     test_browser_config.py       BrowserSettings
#     test_e2e_naver.py            네이버 E2E (브라우저 필요)
#   factory/tests/
#     test_combo_generator.py
#     test_dispatcher.py
#     test_selection.py
#
# 사용법
# ------
#   (없음)       unit 전체 (빠름, 브라우저 불필요)
#   --factory    factory 단위 테스트
#   --e2e        unit + factory + e2e smoke
#   --pipeline   파이프라인 통합 (모든 옵션)
#   --real-run   실제 발행 (ENV=production 필요)
#   --all        전체 (e2e + pipeline 포함)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

cd "${PROJECT_ROOT}"

if [ ! -d "${VENV_DIR}" ]; then
    echo "❌ .venv 없음 — bash ./run/init.sh 먼저 실행하세요"
    exit 1
fi
source "${VENV_DIR}/bin/activate"

MODE="${1:---unit}"

case "${MODE}" in

  --unit)
    echo "── [1/5] unit ───────────────────────────"
    pytest -m unit -v
    ;;

  --factory)
    echo "── factory unit ─────────────────────────"
    pytest factory/tests/ -v
    ;;

  --e2e)
    echo "── [1/3] unit ───────────────────────────"
    pytest -m unit -v
    echo ""
    echo "── [2/3] factory unit ───────────────────"
    pytest factory/tests/ -v
    echo ""
    echo "── [3/3] e2e smoke ──────────────────────"
    pytest tests/test_e2e_naver.py -m "e2e and not slow" -v
    ;;

  --pipeline)
    echo "── pipeline — test_pipeline_all_options ─"
    pytest tests/test_e2e_naver.py::test_pipeline_all_options \
      -m "e2e and slow" -v -s
    ;;

  --real-run)
    echo "── real publish ─────────────────────────"
    echo "  ⚠️  실제 발행됩니다. ENV=production + GEMINI_API_KEY 확인하세요."
    echo ""
    pytest tests/test_e2e_naver.py::test_pipeline_real_publish \
      -m "e2e and slow" -v -s --real-run
    ;;

  --all)
    echo "── [1/5] unit ───────────────────────────"
    pytest -m unit -v

    echo ""
    echo "── [2/5] factory unit ───────────────────"
    pytest factory/tests/ -v

    echo ""
    echo "── [3/5] e2e smoke ──────────────────────"
    pytest tests/test_e2e_naver.py -m "e2e and not slow" -v

    echo ""
    echo "── [4/5] options publish e2e ────────────"
    pytest tests/test_options_publish.py -m "e2e" -v -s

    echo ""
    echo "── [5/5] pipeline ───────────────────────"
    pytest tests/test_e2e_naver.py::test_pipeline_all_options \
      -m "e2e and slow" -v -s
    ;;

  --help|-h)
    echo ""
    echo "  bash ./run/test.sh               # unit 전체"
    echo "  bash ./run/test.sh --factory     # factory unit"
    echo "  bash ./run/test.sh --e2e         # unit + factory + e2e smoke"
    echo "  bash ./run/test.sh --pipeline    # 파이프라인 통합 (all options)"
    echo "  bash ./run/test.sh --real-run    # 실제 발행 (ENV=production 필요)"
    echo "  bash ./run/test.sh --all         # 전체"
    echo ""
    ;;

  *)
    echo "알 수 없는 옵션: ${MODE}  (--help 로 도움말 확인)"
    exit 1
    ;;

esac

echo ""
echo "✅ 완료"
