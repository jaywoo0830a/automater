"""CLI entry point: ``python -m observer``."""

from __future__ import annotations

import argparse
import logging
import os
import random
import sys


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m observer",
        description="Naver blog rank observation daemon",
    )
    sub = p.add_subparsers(dest="command")
    sub.required = True

    run_p = sub.add_parser("run", help="Start the observer daemon")
    run_p.add_argument(
        "--once", action="store_true",
        help="Run one poll cycle then exit",
    )
    run_p.add_argument("-v", "--verbose", action="store_true")

    test_p = sub.add_parser("test", help="Test a single keyword (no DB)")
    test_p.add_argument("keyword", help="Search keyword")
    test_p.add_argument("blog_id", help="Blog ID to look for")
    test_p.add_argument("--headless", action="store_true", help="Run headless")
    test_p.add_argument("-v", "--verbose", action="store_true")

    status_p = sub.add_parser("status", help="Show today's schedule summary")
    status_p.add_argument("-v", "--verbose", action="store_true")

    init_p = sub.add_parser("init-db", help="Create database tables")
    init_p.add_argument("-v", "--verbose", action="store_true")

    return p.parse_args(argv)


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _load_config() -> dict:
    """Build config from environment variables."""
    mysql_url = os.environ.get(
        "MYSQL_URL",
        "mysql+pymysql://root:automator@localhost:3306/automator",
    )
    return {
        "mysql_url": mysql_url,
        "poll_interval": int(os.environ.get("POLL_INTERVAL", "30")),
        "headless": os.environ.get("HEADLESS", "true").lower() in ("true", "1", "yes"),
        "max_workers": int(os.environ.get("MAX_WORKERS", "4")),
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    _setup_logging(getattr(args, "verbose", False))

    config = _load_config()

    if args.command == "run":
        from observer.daemon import ObserverDaemon

        daemon = ObserverDaemon(config)
        return daemon.run_once() if args.once else daemon.run()

    if args.command == "test":
        from datetime import datetime

        from playwright.sync_api import sync_playwright

        from observer.collector import collect_session_ip, generate_random_fingerprint
        from observer.human import human_click_element, human_delay
        from observer.searcher import NaverSearcher
        from observer.visitor import PostVisitor

        fp = generate_random_fingerprint()
        print(f"Fingerprint: {fp['hash']}")
        print(f"  UA: {fp['user_agent'][:60]}...")
        print(f"  Viewport: {fp['viewport_width']}x{fp['viewport_height']}")

        from automator.browser import build_context
        from automator.stealth import DEFAULT_FINGERPRINT

        browser_config = {
            "viewport": [fp["viewport_width"], fp["viewport_height"]],
            "user_agent": fp["user_agent"],
            "locale": "ko-KR",
            "timezone": "Asia/Seoul",
            "fingerprint": dict(DEFAULT_FINGERPRINT),
        }

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=args.headless)
            ctx = build_context(browser, browser_config)
            page = ctx.new_page()

            try:
                ip = collect_session_ip(page)
                print(f"  IP: {ip}")

                print(f"\nSearching: {args.keyword!r} (blog_id={args.blog_id})")
                searcher = NaverSearcher(page)
                result = searcher.search(args.keyword, args.blog_id)

                if result.found:
                    print(f"  FOUND at rank {result.rank} ({result.found_in})")
                    print(f"  URL: {result.result_url}")

                    print("\nClicking into post...")
                    human_delay(0.5, 1.0)

                    with ctx.expect_page() as new_page_info:
                        human_click_element(page, result.element)

                    blog_page = new_page_info.value
                    blog_page.wait_for_load_state("load")
                    human_delay(1.0, 2.0)

                    print("Visiting post...")
                    visitor = PostVisitor(blog_page)
                    vd = visitor.visit_current_page()
                    print(f"  Scroll: {vd.scroll_pct:.0%}")
                    print(f"  Dwell: {vd.dwell_seconds:.1f}s")
                    print(f"  Entered: {vd.entered_at}")
                    print(f"  Exited: {vd.exited_at}")

                    human_delay(0.5, 1.0)
                    blog_page.close()

                    # Linger on search results before leaving
                    print("Lingering on search results...")
                    human_delay(1.5, 3.0)
                    page.mouse.wheel(0, random.randint(100, 300))
                    human_delay(1.0, 2.0)
                else:
                    print("  NOT FOUND")
            finally:
                ctx.close()
                browser.close()

        print("\nDone.")
        return 0

    if args.command == "status":
        from observer.store import ObserverStore

        store = ObserverStore(config["mysql_url"])
        store.print_status()
        return 0

    if args.command == "init-db":
        from observer.store import ObserverStore

        store = ObserverStore(config["mysql_url"])
        store.create_tables()
        print("Database tables created.")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
