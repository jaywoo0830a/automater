"""Integration tests: CLI reliably writes observer_results.jsonl.

The CLI's ``_append_observer_result`` is the contract point between
the CLI (producer) and the API Worker (consumer). These tests pin
down the exact file format and ensure:
- file is created in the workspace directory
- one JSON line per successful combo
- UTF-8 Korean text survives round-trip
- concurrent/repeated appends don't corrupt the file
- failure paths don't raise (silent degradation)
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from cli.campaign_executor import _append_observer_result, _extract_keyword


@pytest.fixture
def workspace(tmp_path):
    """Return a dict that looks like a loaded config with _base_dir."""
    return {"_base_dir": str(tmp_path), "keywords": {"region": []}}


def _read_jsonl(workspace) -> list[dict]:
    path = Path(workspace["_base_dir"]) / "observer_results.jsonl"
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


# ── file creation ───────────────────────────────────────────────────

def test_creates_jsonl_in_workspace_dir(workspace):
    _append_observer_result(
        workspace,
        blog_id="myblog",
        keyword="test",
        title="title",
        published_at=datetime(2026, 4, 17, 14, 0),
    )
    path = Path(workspace["_base_dir"]) / "observer_results.jsonl"
    assert path.exists()


def test_each_combo_adds_one_line(workspace):
    for i in range(5):
        _append_observer_result(
            workspace,
            blog_id="myblog",
            keyword=f"kw{i}",
            title=f"title {i}",
            published_at=datetime(2026, 4, 17, 14, 0),
        )
    entries = _read_jsonl(workspace)
    assert len(entries) == 5


# ── content correctness ─────────────────────────────────────────────

def test_records_all_required_fields(workspace):
    _append_observer_result(
        workspace,
        blog_id="myblog",
        keyword="keyword",
        title="title",
        published_at=datetime(2026, 4, 17, 14, 30),
    )
    [entry] = _read_jsonl(workspace)
    assert entry["blog_id"] == "myblog"
    assert entry["keyword"] == "keyword"
    assert entry["title"] == "title"
    assert entry["published_at"] == "2026-04-17T14:30:00"


def test_preserves_korean_text(workspace):
    _append_observer_result(
        workspace,
        blog_id="tzzvubwhlf14803",
        keyword="산본동 중등 수학학원",
        title="수리동 중등 수학학원 강력 추천",
        published_at=datetime(2026, 4, 17, 14, 0),
    )
    [entry] = _read_jsonl(workspace)
    assert entry["keyword"] == "산본동 중등 수학학원"
    assert entry["title"] == "수리동 중등 수학학원 강력 추천"


def test_null_published_at_stored_as_null(workspace):
    _append_observer_result(
        workspace,
        blog_id="myblog",
        keyword="k",
        title="t",
        published_at=None,
    )
    [entry] = _read_jsonl(workspace)
    assert entry["published_at"] is None


# ── append semantics ────────────────────────────────────────────────

def test_appends_do_not_truncate_existing(workspace):
    """Ensure the file is opened in append mode, not write mode."""
    _append_observer_result(
        workspace, blog_id="b1", keyword="k1", title="t1",
        published_at=datetime(2026, 4, 17, 14, 0),
    )
    _append_observer_result(
        workspace, blog_id="b2", keyword="k2", title="t2",
        published_at=datetime(2026, 4, 17, 14, 15),
    )
    entries = _read_jsonl(workspace)
    assert len(entries) == 2
    assert entries[0]["blog_id"] == "b1"
    assert entries[1]["blog_id"] == "b2"


def test_each_line_is_valid_json_independently(workspace):
    """Worker parses line-by-line — each line must be standalone valid JSON."""
    _append_observer_result(
        workspace, blog_id="b1", keyword="k1", title="t1",
        published_at=datetime(2026, 4, 17, 14, 0),
    )
    _append_observer_result(
        workspace, blog_id="b2", keyword="k2", title="t2",
        published_at=datetime(2026, 4, 17, 14, 15),
    )
    raw = (Path(workspace["_base_dir"]) / "observer_results.jsonl").read_text(
        encoding="utf-8",
    )
    for line in raw.splitlines():
        if line.strip():
            # must not raise
            json.loads(line)


# ── failure handling ────────────────────────────────────────────────

def test_does_not_raise_when_base_dir_missing():
    """Silent degradation — CLI must never crash because of observer logging."""
    config = {"_base_dir": "/nonexistent/path/that/should/not/exist"}
    # Must NOT raise
    _append_observer_result(
        config, blog_id="b", keyword="k", title="t", published_at=None,
    )


def test_uses_current_dir_when_base_dir_absent(tmp_path, monkeypatch):
    """Default _base_dir is '.' — should fall back gracefully."""
    monkeypatch.chdir(tmp_path)
    _append_observer_result(
        {}, blog_id="b", keyword="k", title="t", published_at=None,
    )
    assert (tmp_path / "observer_results.jsonl").exists()


# ── integration with _extract_keyword ───────────────────────────────

def test_extract_keyword_matches_jsonl_keyword_field(workspace):
    """The keyword written to jsonl should come from _extract_keyword."""
    combo_values = {"region": "수리동", "subject": "중등 수학학원"}
    config = {"_base_dir": workspace["_base_dir"],
              "keywords": {"region": [], "subject": []}}

    extracted = _extract_keyword(combo_values, config)
    _append_observer_result(
        config, blog_id="b", keyword=extracted, title="t", published_at=None,
    )
    [entry] = _read_jsonl(config)
    assert entry["keyword"] == extracted
    assert "수리동" in entry["keyword"]
    assert "중등 수학학원" in entry["keyword"]
