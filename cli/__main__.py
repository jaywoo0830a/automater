"""
cli/__main__.py
----------------
Entry point: python -m cli campaign.yaml [options]

Modes:
    (default)   Dry-run — builds specs, prints titles, no publishing.
    --execute   Live execution — publishes through Playwright.
    --preview   Show combo count, account assignments, sample titles.
    --validate  Validate config only, no execution.

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


def _build_live_executor(
    config: dict[str, Any],
    args: argparse.Namespace,
) -> CampaignExecutor:
    """Build executor with live runner and editor factory."""
    import os
    from automator.spec_validator import SpecValidator
    from automator.content_builder import ContentBuilder
    from automator.runner import JobRunner

    env = os.getenv("ENV", "dev")
    if env == "production":
        from automator.gemini_generator import GeminiGenerator
        text_gen = GeminiGenerator()
    else:
        from automator.stubs import StubTextGenerator
        text_gen = StubTextGenerator()

    from automator.local_processor import LocalImageProcessor
    runner = JobRunner(SpecValidator(), ContentBuilder(text_gen, LocalImageProcessor()))

    from cli.session_store import create_session_store

    store_url = config.get("session_store")
    session_store = create_session_store(store_url)

    def editor_factory(account: dict[str, Any]):
        from playwright.sync_api import sync_playwright
        from automator.smart_editor import SmartEditorOne

        headless = config.get("run", {}).get("headless", True)
        if args.headless:
            headless = True
        elif args.no_headless:
            headless = False

        pw = sync_playwright().start()
        browser = pw.chromium.launch(
            headless=headless,
            slow_mo=config.get("run", {}).get("slow_mo", 0),
        )

        username = account["username"]
        explicit_path = account.get("session", "")
        state = None

        # Load session: explicit path takes priority, then store by key
        if explicit_path:
            state = session_store.load_path(explicit_path) if hasattr(session_store, "load_path") else session_store.load(username)
        else:
            state = session_store.load(username)

        if state:
            ctx = browser.new_context(
                storage_state=state,
                locale="ko-KR",
                timezone_id="Asia/Seoul",
            )
        else:
            ctx = browser.new_context(
                locale="ko-KR",
                timezone_id="Asia/Seoul",
            )
            _auto_login(ctx, account)

            # Save session: explicit path or store by key
            new_state = ctx.storage_state()
            if explicit_path and hasattr(session_store, "save_path"):
                session_store.save_path(explicit_path, new_state)
            else:
                session_store.save(username, new_state)
            log.info("Session saved for %s", username)

        page = ctx.new_page()
        blog_id = account.get("blog_id", username)
        write_url = f"https://blog.naver.com/{blog_id}?Redirect=Write&"
        return SmartEditorOne(page, write_url, dry_run=False)

    return CampaignExecutor(runner=runner, editor_factory=editor_factory)


def _auto_login(ctx, account: dict[str, Any]) -> None:
    """Log in to Naver with username/password, then close the login page."""
    from automator.selector_loader import SelectorLoader

    log = logging.getLogger("cli")
    log.info("No session found — logging in as %s", account["username"])

    login_sel = SelectorLoader.load("selectors/naver/login.json")
    page = ctx.new_page()
    page.goto("https://nid.naver.com/nidlogin.login")

    login_sel.locator(page, "naver_login_id").fill(account["username"])
    login_sel.locator(page, "naver_login_pw").fill(account["password"])
    login_sel.locator(page, "naver_login_submit").click()

    page.wait_for_url(lambda url: "nidlogin" not in url, timeout=15_000)
    page.close()


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
    if result.errors:
        print(f"\n  Errors:")
        for e in result.errors:
            print(f"    - {e}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    sys.exit(main())
