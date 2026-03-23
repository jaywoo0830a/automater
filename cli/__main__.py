"""
cli/__main__.py
----------------
Entry point: python -m cli campaign.json [options]

Modes:
    (default)   Dry-run — builds specs, prints titles, no publishing.
    --execute   Live execution — publishes through Playwright.
    --preview   Show combo count, account assignments, sample titles.
    --validate  Validate JSON only, no execution.

Options:
    --limit N            Process at most N combinations.
    --account USERNAME   Use only this account (repeatable).
    --schedule-base DT   Base datetime for scheduling (KST, ISO format).
    --headless / --no-headless   Override browser headless mode.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone

from cli.campaign_config import AccountEntry, CampaignConfig
from cli.config_loader import ConfigError, load_config
from cli.campaign_executor import CampaignExecutor

KST = timezone(timedelta(hours=9))


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns exit code."""
    args = _parse_args(argv)
    _setup_logging(verbose=args.verbose)

    logger = logging.getLogger("cli")

    # Load and validate
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        logger.error("Config error: %s", exc)
        return 1

    logger.info("Config loaded: %s", args.config)

    # Filter accounts if --account specified
    if args.account:
        config = _filter_accounts(config, args.account)
        if not config.accounts:
            logger.error(
                "No matching accounts found for: %s", args.account,
            )
            return 1

    # Validate-only mode
    if args.validate:
        logger.info("Validation passed.")
        return 0

    executor = CampaignExecutor()

    # Preview mode
    if args.preview:
        plan = executor.preview(config, limit=args.limit)
        _print_plan(plan)
        return 0

    # Dry-run (default) or live execution
    if args.execute:
        executor = _build_live_executor(config, args)
        logger.info("LIVE execution mode — posts will be published!")
    else:
        logger.info("Dry-run mode (use --execute for live publishing)")

    result = executor.execute(
        config,
        dry_run=not args.execute,
        limit=args.limit,
    )

    _print_result(result)
    return 0 if result.total_failed == 0 else 1


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m cli",
        description="JSON-driven blog campaign executor.",
    )
    parser.add_argument(
        "config",
        help="Path to campaign JSON file.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Live execution (default is dry-run).",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Show execution plan without running.",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate JSON only.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of combinations to process.",
    )
    parser.add_argument(
        "--account",
        action="append",
        default=[],
        help="Use only this account (repeatable).",
    )
    parser.add_argument(
        "--schedule-base",
        type=str,
        default=None,
        help="Base datetime for scheduling (KST, ISO format).",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=None,
        help="Force headless browser mode.",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Force visible browser mode.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def _filter_accounts(
    config: CampaignConfig,
    usernames: list[str],
) -> CampaignConfig:
    """Return a new config with only the specified accounts."""
    name_set = set(usernames)
    filtered = tuple(a for a in config.accounts if a.username in name_set)

    # CampaignConfig is frozen — rebuild with filtered accounts
    return CampaignConfig(
        accounts=filtered,
        title=config.title,
        keywords=config.keywords,
        palettes=config.palettes,
        layout=config.layout,
        media=config.media,
        publish_config=config.publish_config,
        run_config=config.run_config,
    )


def _build_live_executor(
    config: CampaignConfig,
    args: argparse.Namespace,
) -> CampaignExecutor:
    """Build a CampaignExecutor with live runner and editor factory."""
    from automator.stubs import StubTextGenerator, NoopImageProcessor
    from automator.spec_validator import SpecValidator
    from automator.content_builder import ContentBuilder
    from automator.runner import JobRunner

    # Determine text generator based on ENV
    import os
    env = os.getenv("ENV", "dev")
    if env == "production":
        from automator.gemini_generator import GeminiGenerator
        text_gen = GeminiGenerator()
    else:
        text_gen = StubTextGenerator()

    from automator.local_processor import LocalImageProcessor
    img_proc = LocalImageProcessor()

    runner = JobRunner(SpecValidator(), ContentBuilder(text_gen, img_proc))

    def editor_factory(account_entry: AccountEntry):
        from playwright.sync_api import sync_playwright
        from automator.smart_editor import SmartEditorOne

        headless = config.run_config.get("headless", True)
        if args.headless is True:
            headless = True
        elif args.no_headless:
            headless = False

        # Lazy browser management — real implementation would
        # share browser instances across accounts
        pw = sync_playwright().start()
        browser = pw.chromium.launch(
            headless=headless,
            slow_mo=config.run_config.get("slow_mo", 0),
        )

        session_path = (
            account_entry.session_path
            or f"{account_entry.username}_session.json"
        )
        ctx = browser.new_context(
            storage_state=session_path if os.path.exists(session_path) else None,
            locale="ko-KR",
            timezone_id="Asia/Seoul",
        )
        page = ctx.new_page()

        blog_id = account_entry.meta.get("blog_id", account_entry.username)
        write_url = f"https://blog.naver.com/{blog_id}?Redirect=Write&"

        return SmartEditorOne(page, write_url, dry_run=False)

    return CampaignExecutor(runner=runner, editor_factory=editor_factory)


def _print_plan(plan) -> None:
    """Print execution plan to stdout."""
    print(f"\n{'='*50}")
    print(f"  Execution Plan")
    print(f"{'='*50}")
    print(f"  Total combinations : {plan.total_combos}")
    print(f"  Accounts used      : {plan.accounts_used}")
    print()
    for item in plan.items:
        print(f"    {item.account_username}: {item.combo_count} posts")
    if plan.sample_titles:
        print(f"\n  Sample titles:")
        for title in plan.sample_titles:
            print(f"    • {title}")
    print(f"{'='*50}\n")


def _print_result(result) -> None:
    """Print execution result to stdout."""
    print(f"\n{'='*50}")
    print(f"  Execution Result")
    print(f"{'='*50}")
    print(f"  Attempted : {result.total_attempted}")
    print(f"  Succeeded : {result.total_succeeded}")
    print(f"  Failed    : {result.total_failed}")
    if result.errors:
        print(f"\n  Errors:")
        for err in result.errors:
            print(f"    • {err}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    sys.exit(main())
