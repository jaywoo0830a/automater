#!/usr/bin/env bash
# run/test.sh — 테스트 실행
#
#   (없음)             unit 테스트 (빠름, 브라우저 불필요)
#   --factory          factory 단위 테스트
#   --e2e              unit + factory + e2e smoke
#   --schedule         예약 발행 UI e2e
#   --pipeline         파이프라인 통합 테스트 (모든 옵션)
#   --all              전체
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

UNIT_TESTS=(
    tests/test_job_unit.py
    tests/test_editor_unit.py
    tests/test_selector_unit.py
    tests/test_config.py
    tests/test_title_unit.py
    tests/test_layout_unit.py
    tests/test_paragraph_generator.py
    tests/test_seo_option.py
    tests/test_seo_job_integration.py
    tests/test_image_processor.py
    tests/test_image_job_integration.py
    tests/test_asset_loader.py
)

FACTORY_TESTS=(
    factory/tests/test_combo_generator.py
    factory/tests/test_dispatcher.py
    factory/tests/test_selection.py
)

cd "${PROJECT_ROOT}"

if [ ! -d "${VENV_DIR}" ]; then
    echo "❌ .venv 없음 — bash ./run/init.sh 먼저 실행하세요"
    exit 1
fi
source "${VENV_DIR}/bin/activate"

MODE="${1:---unit}"

case "${MODE}" in

  --unit)
    echo "── unit ─────────────────────────────────"
    pytest "${UNIT_TESTS[@]}" -m unit -v
    ;;

  --factory)
    echo "── factory unit ─────────────────────────"
    pytest "${FACTORY_TESTS[@]}" -v
    ;;

  --e2e)
    echo "── [1/3] unit ───────────────────────────"
    pytest "${UNIT_TESTS[@]}" -m unit -v
    echo ""
    echo "── [2/3] factory unit ───────────────────"
    pytest "${FACTORY_TESTS[@]}" -v
    echo ""
    echo "── [3/3] e2e smoke ──────────────────────"
    pytest tests/test_blog_e2e.py -m "e2e and not slow" -v
    ;;

  --schedule)
    echo "── schedule e2e (dry_run=True) ──────────"
    pytest tests/test_schedule_e2e.py -m "e2e" -v -s
    ;;

  --pipeline)
    echo "── pipeline — test_pipeline_all_options ─"
    pytest tests/test_blog_e2e.py::test_pipeline_all_options -m "e2e and slow" -v -s
    ;;

  --real-run)
    echo "── real publish — test_pipeline_real_publish ─"
    echo "  ⚠️  실제 발행됩니다. ENV=production + GEMINI_API_KEY 확인하세요."
    echo ""
    pytest tests/test_blog_e2e.py::test_pipeline_real_publish \
      -m "e2e and slow" -v -s --real-run
    ;;

  --all)
    echo "── [1/5] unit ───────────────────────────"
    pytest "${UNIT_TESTS[@]}" -m unit -v

    echo ""
    echo "── [2/5] factory unit ───────────────────"
    pytest "${FACTORY_TESTS[@]}" -v

    echo ""
    echo "── [3/5] e2e smoke ──────────────────────"
    pytest tests/test_blog_e2e.py -m "e2e and not slow" -v

    echo ""
    echo "── [4/5] schedule e2e ───────────────────"
    pytest tests/test_schedule_e2e.py -m "e2e" -v -s

    echo ""
    echo "── [5/5] pipeline ───────────────────────"
    pytest tests/test_blog_e2e.py::test_pipeline_all_options -m "e2e and slow" -v -s
    ;;

  --help|-h)
    echo ""
    echo "  bash ./run/test.sh                  # unit"
    echo "  bash ./run/test.sh --factory        # factory unit"
    echo "  bash ./run/test.sh --e2e            # unit + factory + e2e smoke"
    echo "  bash ./run/test.sh --schedule       # 예약 발행 e2e"
    echo "  bash ./run/test.sh --pipeline       # 파이프라인 통합 (모든 옵션)
  bash ./run/test.sh --real-run       # 실제 발행 (ENV=production 필요)"
    echo "  bash ./run/test.sh --all            # 전체"
    echo ""
    ;;

  *)
    echo "알 수 없는 옵션: ${MODE}  (--help 로 도움말 확인)"
    exit 1
    ;;

esac

echo ""
echo "✅ 완료"
