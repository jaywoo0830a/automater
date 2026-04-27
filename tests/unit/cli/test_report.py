"""
tests/unit/cli/test_report.py
------------------------------
Report writer — YAML 강제 출력.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from cli.report import write_report, write_rows


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _record(**kw):
    defaults = {
        "blog_id": "blog1",
        "keyword": "가경동 수학학원",
        "title": "가경동 수학학원 한눈 추천",
        "published_at": datetime(2026, 4, 27, 14, 30),
    }
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _result(succeeded=None, failed=None):
    return SimpleNamespace(
        succeeded_combos=succeeded or [],
        failed_combos=failed or [],
    )


# ---------------------------------------------------------------------------
# write_rows — YAML 강제
# ---------------------------------------------------------------------------

class TestWriteRowsYamlForced:

    def test_yaml_path_kept(self, tmp_path: Path):
        out = tmp_path / "report.yaml"
        result = write_rows([{"blog_id": "b", "keyword": "k", "title": "t", "published_at": ""}], out)
        assert result.suffix == ".yaml"
        assert result.exists()

    def test_yml_path_kept(self, tmp_path: Path):
        out = tmp_path / "report.yml"
        result = write_rows([{"blog_id": "b", "keyword": "k", "title": "t", "published_at": ""}], out)
        assert result.suffix == ".yml"
        assert result.exists()

    def test_xlsx_path_coerced_to_yaml(self, tmp_path: Path):
        out = tmp_path / "report.xlsx"
        result = write_rows([{"blog_id": "b", "keyword": "k", "title": "t", "published_at": ""}], out)
        assert result.suffix == ".yaml"
        assert result.exists()
        assert not out.exists()  # 원래 .xlsx 경로엔 파일이 없어야 함

    def test_unknown_extension_coerced_to_yaml(self, tmp_path: Path):
        out = tmp_path / "report.txt"
        result = write_rows([{"blog_id": "b", "keyword": "k", "title": "t", "published_at": ""}], out)
        assert result.suffix == ".yaml"

    def test_no_extension_coerced_to_yaml(self, tmp_path: Path):
        out = tmp_path / "report"
        result = write_rows([{"blog_id": "b", "keyword": "k", "title": "t", "published_at": ""}], out)
        assert result.suffix == ".yaml"

    def test_creates_parent_dirs(self, tmp_path: Path):
        out = tmp_path / "deep" / "nested" / "report.yaml"
        result = write_rows([], out)
        assert result.exists()


# ---------------------------------------------------------------------------
# write_report — content
# ---------------------------------------------------------------------------

class TestWriteReportContent:

    def test_writes_succeeded_only_by_default(self, tmp_path: Path):
        out = tmp_path / "r.yaml"
        succ = [_record(keyword="가경동 수학학원")]
        fail = [_record(keyword="실패동")]
        write_report(_result(succeeded=succ, failed=fail), out)
        rows = yaml.safe_load(out.read_text(encoding="utf-8"))
        assert len(rows) == 1
        assert rows[0]["keyword"] == "가경동 수학학원"

    def test_include_failed(self, tmp_path: Path):
        out = tmp_path / "r.yaml"
        succ = [_record(keyword="성공")]
        fail = [_record(keyword="실패")]
        write_report(_result(succeeded=succ, failed=fail), out, include_failed=True)
        rows = yaml.safe_load(out.read_text(encoding="utf-8"))
        assert [r["keyword"] for r in rows] == ["성공", "실패"]

    def test_field_order(self, tmp_path: Path):
        out = tmp_path / "r.yaml"
        write_report(_result(succeeded=[_record()]), out)
        rows = yaml.safe_load(out.read_text(encoding="utf-8"))
        assert list(rows[0].keys()) == ["blog_id", "keyword", "title", "published_at"]

    def test_published_at_isoformat(self, tmp_path: Path):
        out = tmp_path / "r.yaml"
        rec = _record(published_at=datetime(2026, 4, 27, 14, 30))
        write_report(_result(succeeded=[rec]), out)
        rows = yaml.safe_load(out.read_text(encoding="utf-8"))
        assert rows[0]["published_at"] == "2026-04-27T14:30:00"

    def test_published_at_none_becomes_empty(self, tmp_path: Path):
        out = tmp_path / "r.yaml"
        rec = _record(published_at=None)
        write_report(_result(succeeded=[rec]), out)
        rows = yaml.safe_load(out.read_text(encoding="utf-8"))
        assert rows[0]["published_at"] == ""

    def test_unicode_preserved(self, tmp_path: Path):
        out = tmp_path / "r.yaml"
        rec = _record(keyword="가경동 수학학원", title="가경동 수학학원 한눈 추천")
        write_report(_result(succeeded=[rec]), out)
        text = out.read_text(encoding="utf-8")
        # allow_unicode=True 이므로 한글이 그대로 들어가야 함
        assert "가경동 수학학원" in text

    def test_xlsx_path_writes_yaml(self, tmp_path: Path):
        """엑셀 경로를 넘겨도 .yaml 로 저장된다."""
        out = tmp_path / "r.xlsx"
        rec = _record()
        saved = write_report(_result(succeeded=[rec]), out)
        assert saved.suffix == ".yaml"
        rows = yaml.safe_load(saved.read_text(encoding="utf-8"))
        assert len(rows) == 1
