"""
factory/main.py
----------------
CLI entry point for the factory pipeline.

Commands:
    python -m factory.main seed        -- combinations 테이블 채우기
    python -m factory.main dispatch    -- 가용 계정에 배치 할당
    python -m factory.main run         -- pending 배치 병렬 실행
    python -m factory.main status      -- 현재 진행 상황 출력
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from sqlalchemy import func
from sqlalchemy.orm import Session

from factory.db import get_engine
from factory.logging_config import setup as setup_logging

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
setup_logging()

KST = timezone(timedelta(hours=9))


def cmd_seed(_args) -> None:
    from factory.combo_generator import ComboGenerator
    from factory.keyword_picker import CampaignKeywordPicker

    campaign_id = int(os.environ.get("CAMPAIGN_ID", "1"))
    engine      = get_engine()

    with Session(engine) as session, session.begin():
        picker   = CampaignKeywordPicker(session=session, campaign_id=campaign_id)
        picks    = picker.get_picked_keyword_ids()
        gen      = ComboGenerator(session=session, campaign_id=campaign_id, picks=picks)
        inserted = gen.run()
        active   = {k: v for k, v in picker.list_picks().items() if v}

    if active:
        print(f"  선택 필터: {active}")
    else:
        print(f"  선택 필터: 없음 (전체)")
    print(f"✅ seed: {inserted}개 조합 추가")


def cmd_select(args) -> None:
    from factory.keyword_picker import CampaignKeywordPicker

    campaign_id = int(os.environ.get("CAMPAIGN_ID", "1"))
    engine      = get_engine()

    with Session(engine) as session, session.begin():
        sel = CampaignKeywordPicker(session=session, campaign_id=campaign_id)

        if args.list:
            result = sel.list_picks()
            print(f"\n  캠페인 {campaign_id} 현재 선택:")
            for slug, values in result.items():
                if values:
                    print(f"    {slug:15s}: {', '.join(values)}")
                else:
                    print(f"    {slug:15s}: (전체 사용)")
            return

        if not args.dimension or args.values is None:
            print("❌ --dimension 과 --values 를 함께 지정하세요.")
            return

        values = [v.strip() for v in args.values.split(",")] if args.values else []
        count  = sel.pick(category_slug=args.dimension, values=values)

    if values:
        print(f"✅ '{args.dimension}' → {values} ({count}개) 선택 완료")
    else:
        print(f"✅ '{args.dimension}' 선택 초기화 (전체 사용)")


def cmd_dispatch(args) -> None:
    from factory.dispatcher import BatchDispatcher

    if args.schedule_at:
        base = datetime.strptime(args.schedule_at, "%Y-%m-%d %H:%M").replace(tzinfo=KST)
    else:
        now  = datetime.now(tz=KST)
        base = (now + timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)

    engine = get_engine()
    with Session(engine) as session, session.begin():
        result = BatchDispatcher(session=session, schedule_base=base).dispatch()

    print(f"✅ dispatch: {result}")


def cmd_run(args) -> None:
    from factory.runner import FactoryRunner

    runner = FactoryRunner(
        db_url  = get_engine().url.render_as_string(hide_password=False),
        workers = args.workers,
        dry_run = args.dry_run,
    )
    print(f"✅ run: {runner.run()}")


def cmd_status(_args) -> None:
    from factory.models import Batch, Combination, Account

    engine = get_engine()
    with Session(engine) as session:
        batch_rows = (
            session.query(Batch.status, func.count(Batch.id).label("cnt"))
            .group_by(Batch.status).all()
        )
        combo_total   = session.query(func.count(Combination.id)).scalar()
        combo_pending = session.query(func.count(Combination.id)).filter(Combination.used_at.is_(None)).scalar()
        account_rows  = (
            session.query(Account.status, func.count(Account.id).label("cnt"))
            .group_by(Account.status).all()
        )

    print("\n=== Factory Status ===")
    print("\nBatches:")
    for r in batch_rows:
        print(f"  {r.status:10s}: {r.cnt}")
    print(f"\nCombinations: {combo_total} total, {combo_pending} pending")
    print("\nAccounts:")
    for r in account_rows:
        print(f"  {r.status:10s}: {r.cnt}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="factory")
    parser.add_argument("command", choices=["seed", "select", "dispatch", "run", "status"])
    parser.add_argument("--workers",     type=int, default=5)
    parser.add_argument("--dry-run",     action="store_true")
    parser.add_argument("--schedule-at", type=str, default=None)
    parser.add_argument("--dimension",   type=str, default=None)
    parser.add_argument("--values",      type=str, default=None)
    parser.add_argument("--list",        action="store_true")

    args = parser.parse_args()
    {
        "seed":     cmd_seed,
        "select":   cmd_select,
        "dispatch": cmd_dispatch,
        "run":      cmd_run,
        "status":   cmd_status,
    }[args.command](args)


if __name__ == "__main__":
    main()
