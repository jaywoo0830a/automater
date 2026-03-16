"""
factory/main.py
----------------
CLI entry point for the factory pipeline.

Commands:
    python -m factory.main seed        -- combinations 테이블 채우기
    python -m factory.main dispatch    -- 가용 계정에 배치 할당
    python -m factory.main run         -- pending 배치 병렬 실행
    python -m factory.main status      -- 현재 진행 상황 출력

Options:
    --workers N     병렬 워커 수 (default: 5)
    --dry-run       실제 발행 없이 UI 흐름만 실행
    --schedule-at   첫 배치 예약 시각 KST (default: 2시간 뒤 정각)
                    format: "YYYY-MM-DD HH:MM"
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from factory.logging_config import setup as setup_logging

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
setup_logging()

KST = timezone(timedelta(hours=9))


def _db_config() -> dict:
    return {
        "host":     os.environ.get("DB_HOST",     "127.0.0.1"),
        "port":     int(os.environ.get("DB_PORT", "3306")),
        "database": os.environ.get("DB_NAME",     "automator"),
        "user":     os.environ.get("DB_USER",     "automator"),
        "password": os.environ.get("DB_PASSWORD", "automatorpass"),
    }


def cmd_seed(_args) -> None:
    from factory.db import Database
    from factory.combo_generator import ComboGenerator

    with Database.from_config(**_db_config()) as db:
        gen      = ComboGenerator(db=db)
        inserted = gen.run()
    print(f"✅ seed: {inserted}개 조합 추가")


def cmd_dispatch(args) -> None:
    from factory.db import Database
    from factory.dispatcher import BatchDispatcher

    if args.schedule_at:
        base = datetime.strptime(args.schedule_at, "%Y-%m-%d %H:%M").replace(tzinfo=KST)
    else:
        now  = datetime.now(tz=KST)
        base = (now + timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)

    with Database.from_config(**_db_config()) as db:
        dispatcher = BatchDispatcher(db=db, schedule_base=base)
        result     = dispatcher.dispatch()

    print(f"✅ dispatch: {result}")


def cmd_run(args) -> None:
    from factory.runner import FactoryRunner

    runner = FactoryRunner(
        db_config = _db_config(),
        workers   = args.workers,
        dry_run   = args.dry_run,
    )
    result = runner.run()
    print(f"✅ run: {result}")


def cmd_status(_args) -> None:
    from factory.db import Database

    with Database.from_config(**_db_config()) as db:
        batches = db.fetch_all(
            "SELECT status, COUNT(*) AS cnt FROM batches GROUP BY status"
        )
        combos = db.fetch_one(
            "SELECT COUNT(*) AS total, "
            "SUM(used_at IS NULL) AS pending FROM combinations"
        )
        accounts = db.fetch_all(
            "SELECT status, COUNT(*) AS cnt FROM accounts GROUP BY status"
        )

    print("\n=== Factory Status ===")
    print("\nBatches:")
    for r in batches:
        print(f"  {r['status']:10s}: {r['cnt']}")
    if combos:
        print(f"\nCombinations: {combos['total']} total, {combos['pending']} pending")
    print("\nAccounts:")
    for r in accounts:
        print(f"  {r['status']:10s}: {r['cnt']}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="factory")
    parser.add_argument("command", choices=["seed", "dispatch", "run", "status"])
    parser.add_argument("--workers",     type=int,  default=5)
    parser.add_argument("--dry-run",     action="store_true")
    parser.add_argument("--schedule-at", type=str,  default=None,
                        help='KST datetime e.g. "2026-03-20 14:00"')

    args = parser.parse_args()
    {
        "seed":     cmd_seed,
        "dispatch": cmd_dispatch,
        "run":      cmd_run,
        "status":   cmd_status,
    }[args.command](args)


if __name__ == "__main__":
    main()
