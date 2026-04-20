"""Integration tests: API Worker._register_for_observation reads jsonl → DB.

This is the consumer side of the CLI's observer_results.jsonl contract.
Tests verify:
- Every jsonl line becomes one campaigns row
- Korean text round-trips through DB
- Partial / malformed inputs don't crash the worker
- Missing file / missing env vars are handled gracefully
- UTC datetime parsing is correct
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from automator.models.base import (
    Base,
    create_engine_from_url,
    create_session_factory,
)
from automator.models.campaign import Campaign as DBCampaign
from api.worker import Worker


# ── fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def db_url(tmp_path):
    """File-backed SQLite URL with schema pre-created."""
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine_from_url(url)
    Base.metadata.create_all(engine)
    engine.dispose()
    return url


@pytest.fixture
def campaign(tmp_path):
    """Mock campaign object pointing at a workspace with a jsonl helper."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config_path = workspace / "campaign.yaml"
    config_path.write_text("placeholder: true\n", encoding="utf-8")

    c = MagicMock()
    c.config_path = str(config_path)
    c._emit = MagicMock()

    def _write_jsonl(entries: list[dict]) -> None:
        jsonl = workspace / "observer_results.jsonl"
        with open(jsonl, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")

    c.write_jsonl = _write_jsonl
    return c


@pytest.fixture
def mysql_url(monkeypatch, db_url):
    """Set MYSQL_URL env var for the duration of a test."""
    monkeypatch.setenv("MYSQL_URL", db_url)
    return db_url


def _count_campaigns(db_url: str) -> int:
    engine = create_engine_from_url(db_url)
    Session = create_session_factory(engine)
    try:
        with Session() as session:
            return session.query(DBCampaign).count()
    finally:
        engine.dispose()


def _all_campaigns(db_url: str) -> list[DBCampaign]:
    engine = create_engine_from_url(db_url)
    Session = create_session_factory(engine)
    try:
        with Session() as session:
            rows = session.query(DBCampaign).order_by(DBCampaign.id).all()
            session.expunge_all()
            return rows
    finally:
        engine.dispose()


# ── happy path ──────────────────────────────────────────────────────

def test_inserts_one_row_per_jsonl_line(mysql_url, campaign):
    campaign.write_jsonl([
        {"blog_id": "b1", "keyword": "k1", "title": "t1",
         "published_at": "2026-04-17T14:00:00"},
        {"blog_id": "b2", "keyword": "k2", "title": "t2",
         "published_at": "2026-04-17T14:15:00"},
        {"blog_id": "b3", "keyword": "k3", "title": "t3",
         "published_at": "2026-04-17T14:30:00"},
    ])

    Worker._register_for_observation(campaign)

    assert _count_campaigns(mysql_url) == 3


def test_inserted_fields_match_jsonl(mysql_url, campaign):
    campaign.write_jsonl([
        {"blog_id": "myblog", "keyword": "산본동 수학학원", "title": "title",
         "published_at": "2026-04-17T14:30:00"},
    ])

    Worker._register_for_observation(campaign)

    [row] = _all_campaigns(mysql_url)
    assert row.blog_id == "myblog"
    assert row.keyword == "산본동 수학학원"
    assert row.platform == "naver"
    assert row.published_at == datetime(2026, 4, 17, 14, 30)


def test_korean_text_survives_roundtrip(mysql_url, campaign):
    campaign.write_jsonl([
        {"blog_id": "b", "keyword": "수리동 중등 수학학원 강력 추천",
         "title": "제목", "published_at": "2026-04-17T14:00:00"},
    ])
    Worker._register_for_observation(campaign)

    [row] = _all_campaigns(mysql_url)
    assert row.keyword == "수리동 중등 수학학원 강력 추천"


# ── skip paths (don't crash, don't insert) ─────────────────────────

def test_no_mysql_url_skips_silently(monkeypatch, db_url, campaign):
    monkeypatch.delenv("MYSQL_URL", raising=False)
    campaign.write_jsonl([
        {"blog_id": "b", "keyword": "k", "title": "t", "published_at": None},
    ])
    Worker._register_for_observation(campaign)

    assert _count_campaigns(db_url) == 0


def test_missing_jsonl_file_skips_silently(mysql_url, tmp_path):
    c = MagicMock()
    c.config_path = str(tmp_path / "workspace" / "campaign.yaml")
    c._emit = MagicMock()
    # No crash even though workspace doesn't exist
    Worker._register_for_observation(c)


def test_empty_jsonl_file_skips_silently(mysql_url, campaign):
    campaign.write_jsonl([])
    Worker._register_for_observation(campaign)
    assert _count_campaigns(mysql_url) == 0


def test_blank_lines_are_skipped(mysql_url, campaign):
    """CLI might write trailing newlines; worker must ignore them."""
    workspace_dir = Path(campaign.config_path).parent
    jsonl = workspace_dir / "observer_results.jsonl"
    content = (
        '{"blog_id": "b1", "keyword": "k1", "title": "t1", "published_at": null}\n'
        '\n'
        '   \n'
        '{"blog_id": "b2", "keyword": "k2", "title": "t2", "published_at": null}\n'
        '\n'
    )
    jsonl.write_text(content, encoding="utf-8")

    Worker._register_for_observation(campaign)
    assert _count_campaigns(mysql_url) == 2


# ── error handling ─────────────────────────────────────────────────

def test_malformed_json_does_not_crash(mysql_url, campaign):
    """If any line is malformed, worker should _emit an error and NOT crash."""
    workspace_dir = Path(campaign.config_path).parent
    jsonl = workspace_dir / "observer_results.jsonl"
    jsonl.write_text("{ not valid json\n", encoding="utf-8")

    Worker._register_for_observation(campaign)

    emitted = "\n".join(
        call.args[0] for call in campaign._emit.call_args_list
    )
    assert "[observer]" in emitted


def test_null_published_at_falls_back_to_now(mysql_url, campaign):
    campaign.write_jsonl([
        {"blog_id": "b", "keyword": "k", "title": "t", "published_at": None},
    ])

    before = datetime.utcnow()
    Worker._register_for_observation(campaign)
    after = datetime.utcnow()

    [row] = _all_campaigns(mysql_url)
    assert before <= row.published_at <= after


# ── idempotency hint ───────────────────────────────────────────────

def test_second_call_duplicates_rows(mysql_url, campaign):
    """Documents current (non-idempotent) behaviour: calling twice doubles rows.

    This is intentionally NOT a guarantee — it describes reality so
    future refactors can choose whether to deduplicate.
    """
    campaign.write_jsonl([
        {"blog_id": "b", "keyword": "k", "title": "t", "published_at": None},
    ])

    Worker._register_for_observation(campaign)
    Worker._register_for_observation(campaign)

    assert _count_campaigns(mysql_url) == 2
