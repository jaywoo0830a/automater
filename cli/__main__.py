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

    # Prepare sessions
    if args.prepare:
        return _prepare_sessions(config)

    executor = CampaignExecutor()

    # Preview
    if args.preview:
        plan = executor.preview(config, limit=args.limit)
        _print_plan(plan)
        return 0

    # Execute
    if args.execute:
        executor = _build_live_executor(config, args)
        log.info("LIVE mode — posts will be published!")
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
    mgr = SessionManager(store, pw)
    failed = 0

    for i, account in enumerate(accounts, 1):
        username = account["username"]
        print(f"  [{i}/{total}] {username}")
        try:
            mgr.ensure(account)
            print(f"          ✓ 준비 완료")
        except Exception as exc:
            log.error("  [FAIL] %s: %s", username, exc)
            failed += 1

    pw.stop()

    print(f"\n{'='*50}")
    print(f"  결과: {total - failed} 성공 / {failed} 실패")
    print(f"{'='*50}\n")

    return 0 if failed == 0 else 1


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
    session_mgr = SessionManager(store, pw)

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
        account_browser_cfg = account.get("browser")
        merged_cfg = merge_browser_config(global_browser_cfg, account_browser_cfg)

        browser = pw.chromium.launch(headless=headless, slow_mo=slow_mo)
        ctx = build_context(browser, merged_cfg, storage_state=state)
        page = ctx.new_page()
        blog_id = account.get("blog_id", account["username"])
        write_url = f"https://blog.naver.com/{blog_id}?Redirect=Write&"
        return SmartEditorOne(page, write_url, dry_run=False)

    def session_recovery(account: dict[str, Any]):
        """세션 만료 시 호출 — 새 세션으로 에디터 재생성."""
        _refresh_session(account)
        return editor_factory(account)

    return CampaignExecutor(
        runner=runner,
        editor_factory=editor_factory,
        session_recovery=session_recovery,
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


def _print_result(result) -> None:
    print(f"\n{'='*50}")
    print(f"  Execution Result")
    print(f"{'='*50}")
    print(f"  Attempted : {result.total_attempted}")
    print(f"  Succeeded : {result.total_succeeded}")
    print(f"  Failed    : {result.total_failed}")
    if result.session_recoveries > 0:
        print(f"  Sessions recovered : {result.session_recoveries}")
    if result.errors:
        print(f"\n  Errors:")
        for e in result.errors:
            print(f"    - {e}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    sys.exit(main())
