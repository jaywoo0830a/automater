"""
cli/__main__.py
----------------
Entry point: python -m cli campaign.yaml [options]

Modes:
    (default)   Dry-run — builds specs, prints titles, no publishing.
    --execute   Live execution — publishes through Playwright.
    --preview   Show combo count, account assignments, sample titles.
    --validate  Validate config only, no execution.
    --prepare   Prepare sessions — open browser for manual login per account.

Options:
    --limit N            Process at most N combinations.
    --account USERNAME   Use only this account (repeatable).
    -v, --verbose        Debug logging.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

from cli.config_loader import ConfigError, load_config
from cli.campaign_executor import CampaignExecutor


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns exit code."""
    args = _parse_args(argv)
    _setup_logging(args.verbose)
    log = logging.getLogger("cli")

    # Load
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        log.error("Config error: %s", exc)
        return 1

    log.info("Config loaded: %s", args.config)

    # Filter accounts
    if args.account:
        config = _filter_accounts(config, args.account)
        if not config["accounts"]:
            log.error("No matching accounts: %s", args.account)
            return 1

    # Validate-only
    if args.validate:
        log.info("Validation passed.")
        return 0

    # Pack campaign
    if args.pack is not None:
        return _pack_campaign(config, args.pack)

    # Export sessions
    if args.export_sessions:
        return _export_sessions(config, args.export_sessions)

    # Import sessions
    if args.import_sessions:
        return _import_sessions(config, args.import_sessions)

    # Prepare sessions
    if args.prepare:
        return _prepare_sessions(config)

    executor = CampaignExecutor()

    # Preview
    if args.preview:
        plan = executor.preview(config, limit=args.limit)
        _print_plan(plan)
        return 0

    # --resume flag overrides on_resume to skip
    if args.resume:
        config.setdefault("run", {})["on_resume"] = "skip"
        log.info("Resume mode - skipping completed combos")

    # Execute
    if args.execute:
        executor = _build_live_executor(config, args)
        log.info("LIVE mode - posts will be published!")
    else:
        log.info("Dry-run mode (use --execute for live)")

    result = executor.execute(config, dry_run=not args.execute, limit=args.limit)
    _print_result(result)
    return 0 if result.total_failed == 0 else 1


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m cli",
        description="Campaign DSL executor.",
    )
    p.add_argument("config", help="Path to campaign YAML/JSON file.")
    p.add_argument("--execute", action="store_true", help="Live execution.")
    p.add_argument("--preview", action="store_true", help="Show plan only.")
    p.add_argument("--validate", action="store_true", help="Validate only.")
    p.add_argument("--prepare", action="store_true", help="Prepare sessions (manual login).")
    p.add_argument("--limit", type=int, default=None, help="Max combinations.")
    p.add_argument("--account", action="append", default=[], help="Filter account (repeatable).")
    p.add_argument("--resume", action="store_true", help="Resume: skip completed combos.")
    p.add_argument("--pack", nargs="?", const="", metavar="OUT", help="Pack campaign + assets into ZIP.")
    p.add_argument("--export-sessions", metavar="DIR", help="Export session files to directory.")
    p.add_argument("--import-sessions", metavar="DIR", help="Import session files from directory.")
    p.add_argument("--headless", action="store_true", default=None)
    p.add_argument("--no-headless", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def _filter_accounts(config: dict[str, Any], usernames: list[str]) -> dict[str, Any]:
    name_set = set(usernames)
    filtered = [a for a in config["accounts"] if a["username"] in name_set]
    return {**config, "accounts": filtered}


# ---------------------------------------------------------------------------
# Session prepare
# ---------------------------------------------------------------------------

def _prepare_sessions(config: dict[str, Any]) -> int:
    """세션 준비 모드. SessionManager.ensure()를 각 계정에 호출."""
    from playwright.sync_api import sync_playwright
    from cli.session_store import create_session_store
    from cli.session_manager import SessionManager

    log = logging.getLogger("cli")
    store = create_session_store(config.get("session_store"))
    accounts = config["accounts"]
    total = len(accounts)

    print(f"\n{'='*50}")
    print(f"  세션 준비 ({total}개 계정)")
    print(f"{'='*50}\n")

    pw = sync_playwright().start()
    mgr = SessionManager(store, pw, global_browser_config=config.get("browser", {}))
    failed = 0

    for i, account in enumerate(accounts, 1):
        username = account["username"]
        print(f"  [{i}/{total}] {username}")
        try:
            mgr.ensure(account)
            print(f"          [OK] 준비 완료")
        except Exception as exc:
            log.error("  [FAIL] %s: %s", username, exc)
            failed += 1

    pw.stop()

    print(f"\n{'='*50}")
    print(f"  결과: {total - failed} 성공 / {failed} 실패")
    print(f"{'='*50}\n")

    return 0 if failed == 0 else 1


# ---------------------------------------------------------------------------
# Pack campaign
# ---------------------------------------------------------------------------

def _pack_campaign(config: dict[str, Any], output: str) -> int:
    """캠페인 YAML + 관련 파일을 ZIP으로 패키징."""
    from cli.packer import pack_campaign

    log = logging.getLogger("cli")
    config_path = config["_config_path"]
    output_path = output if output else None

    try:
        zip_path = pack_campaign(config_path, output_path)
        print(f"\n  패키징 완료 → {zip_path}\n")
        return 0
    except Exception as exc:
        log.error("패키징 실패: %s", exc)
        return 1


# ---------------------------------------------------------------------------
# Session export / import
# ---------------------------------------------------------------------------

def _export_sessions(config: dict[str, Any], dest_dir: str) -> int:
    """세션 파일을 지정 디렉터리로 내보내기."""
    import json
    from pathlib import Path
    from cli.session_store import create_session_store

    log = logging.getLogger("cli")
    store = create_session_store(config.get("session_store"))
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)

    accounts = config["accounts"]
    exported = 0

    for account in accounts:
        username = account["username"]
        explicit_path = account.get("session", "")

        if explicit_path and hasattr(store, "load_path"):
            state = store.load_path(explicit_path)
        else:
            state = store.load(username)

        if not state:
            log.warning("[%s] 세션 없음 — 건너뜀", username)
            continue

        out_path = dest / f"{username}.json"
        out_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        exported += 1
        log.info("[%s] → %s", username, out_path)

    print(f"\n  {exported}개 세션 내보내기 완료 → {dest}\n")
    return 0


def _import_sessions(config: dict[str, Any], src_dir: str) -> int:
    """지정 디렉터리에서 세션 파일을 가져오기."""
    import json
    from pathlib import Path
    from cli.session_store import create_session_store

    log = logging.getLogger("cli")
    store = create_session_store(config.get("session_store"))
    src = Path(src_dir)

    if not src.is_dir():
        log.error("디렉터리 없음: %s", src)
        return 1

    accounts = config["accounts"]
    imported = 0

    for account in accounts:
        username = account["username"]
        src_path = src / f"{username}.json"

        if not src_path.exists():
            log.warning("[%s] %s 파일 없음 — 건너뜀", username, src_path)
            continue

        state = json.loads(src_path.read_text(encoding="utf-8"))
        explicit_path = account.get("session", "")

        if explicit_path and hasattr(store, "save_path"):
            store.save_path(explicit_path, state)
        else:
            store.save(username, state)

        imported += 1
        log.info("[%s] ← %s", username, src_path)

    print(f"\n  {imported}개 세션 가져오기 완료 ← {src}\n")
    return 0


# ---------------------------------------------------------------------------
# Live executor builder
# ---------------------------------------------------------------------------

def _build_live_executor(
    config: dict[str, Any],
    args: argparse.Namespace,
) -> CampaignExecutor:
    """Build executor with live runner, editor factory, and session recovery."""
    import os
    from playwright.sync_api import sync_playwright
    from automator.spec_validator import SpecValidator
    from automator.content_builder import ContentBuilder
    from automator.runner import JobRunner
    from cli.session_store import create_session_store
    from cli.session_manager import SessionManager

    log = logging.getLogger("cli")

    env = os.getenv("ENV", "dev")
    if env == "production":
        from automator.gemini_generator import GeminiGenerator
        text_gen = GeminiGenerator()
    else:
        from automator.stubs import StubTextGenerator
        text_gen = StubTextGenerator()

    from automator.local_processor import LocalImageProcessor
    runner = JobRunner(SpecValidator(), ContentBuilder(text_gen, LocalImageProcessor()))

    store = create_session_store(config.get("session_store"))
    pw = sync_playwright().start()
    session_mgr = SessionManager(store, pw, global_browser_config=config.get("browser", {}))

    headless = config.get("run", {}).get("headless", True)
    if args.headless:
        headless = True
    elif args.no_headless:
        headless = False

    slow_mo = config.get("run", {}).get("slow_mo", 0)

    # ── 실행 전 전체 계정 세션 사전 검증 ──
    log.info("세션 사전 검증 시작...")
    for account in config["accounts"]:
        session_mgr.ensure(account)
    log.info("세션 사전 검증 완료")

    # ── 계정별 세션 캐시 (ensure에서 저장된 세션을 재활용) ──
    _session_cache: dict[str, dict] = {}

    def _get_session(account: dict[str, Any]) -> dict:
        username = account["username"]
        if username not in _session_cache:
            _session_cache[username] = session_mgr.ensure(account)
        return _session_cache[username]

    def _refresh_session(account: dict[str, Any]) -> dict:
        username = account["username"]
        state = session_mgr.recover(account)
        _session_cache[username] = state
        return state

    # ── 브라우저 설정 (글로벌 + 계정별 머지) ──
    from automator.browser import build_context, merge_browser_config
    global_browser_cfg = config.get("browser", {})

    def editor_factory(account: dict[str, Any]):
        from automator.smart_editor import SmartEditorOne

        state = _get_session(account)
        account_browser_cfg = account.get("browser") or {}

        # 계정별 프록시를 browser config에 주입
        proxy = account.get("proxy")
        if proxy:
            account_browser_cfg = {**account_browser_cfg, "proxy": proxy}

        merged_cfg = merge_browser_config(global_browser_cfg, account_browser_cfg)

        browser = pw.chromium.launch(headless=headless, slow_mo=slow_mo)
        ctx = build_context(browser, merged_cfg, storage_state=state)
        page = ctx.new_page()
        blog_id = account.get("blog_id", account["username"])
        write_url = f"https://blog.naver.com/{blog_id}?Redirect=Write&"
        return SmartEditorOne(page, write_url, dry_run=False)

    def checker_factory(account: dict[str, Any]):
        from automator.naver_checker import PlaywrightTitleChecker

        tc_config = config.get("title_check", {})
        state = _get_session(account)
        account_browser_cfg = account.get("browser") or {}

        proxy = account.get("proxy")
        if proxy:
            account_browser_cfg = {**account_browser_cfg, "proxy": proxy}

        merged_cfg = merge_browser_config(global_browser_cfg, account_browser_cfg)

        browser = pw.chromium.launch(headless=headless, slow_mo=slow_mo)
        ctx = build_context(browser, merged_cfg, storage_state=state)
        page = ctx.new_page()

        checker = PlaywrightTitleChecker(
            page,
            match=tc_config.get("match", "exact"),
            delay=tc_config.get("delay", "1s ~ 2s"),
        )
        # close()에서 브라우저까지 정리할 수 있도록 참조 보존
        checker._browser = browser  # type: ignore[attr-defined]
        _original_close = checker.close

        def _close_with_browser() -> None:
            _original_close()
            try:
                ctx.close()
                browser.close()
            except Exception:
                pass

        checker.close = _close_with_browser  # type: ignore[method-assign]
        return checker

    return CampaignExecutor(
        runner=runner,
        editor_factory=editor_factory,
        checker_factory=checker_factory,
    )


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _print_plan(plan) -> None:
    print(f"\n{'='*50}")
    print(f"  Execution Plan")
    print(f"{'='*50}")
    print(f"  Total combinations : {plan.total_combos}")
    print(f"  Accounts used      : {plan.accounts_used}")
    for item in plan.items:
        print(f"    {item.account_username}: {item.combo_count} posts")
    if plan.sample_titles:
        print(f"\n  Sample titles:")
        for t in plan.sample_titles:
            print(f"    - {t}")
    print(f"{'='*50}\n")


def _format_combo(values: dict[str, str]) -> str:
    """키워드 조합을 'key=value, ...' 형식으로 포맷."""
    return ", ".join(f"{k}={v}" for k, v in values.items())


def _print_result(result) -> None:
    print(f"\n{'='*50}")
    print(f"  캠페인 실행 결과")
    print(f"{'='*50}")
    print(f"  성공 : {result.total_succeeded} / {result.total_attempted}")
    print(f"  실패 : {result.total_failed} / {result.total_attempted}")

    if result.succeeded_combos:
        print(f"\n  ✓ 성공한 조합 ({len(result.succeeded_combos)}건):")
        for rec in result.succeeded_combos:
            print(f"    [{_format_combo(rec.combo_values)}]")

    if result.failed_combos:
        print(f"\n  ✗ 실패한 조합 ({len(result.failed_combos)}건):")
        for rec in result.failed_combos:
            print(f"    [{_format_combo(rec.combo_values)}]")
            if rec.error:
                print(f"      → {rec.error[:120]}")

    print(f"{'='*50}\n")


if __name__ == "__main__":
    sys.exit(main())
