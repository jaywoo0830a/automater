"""
tests/unit/api/test_report_download.py
----------------------------------------
GET /campaigns/<id>/report — 리포트 다운로드 엔드포인트.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from api.app import app, worker
from api.worker import Campaign, Status


@pytest.fixture
def client(monkeypatch):
    # API_KEY 미설정 시 auth.py 가 인증을 건너뛴다 — 테스트에서 그 모드 사용.
    monkeypatch.delenv("API_KEY", raising=False)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def campaign(tmp_path: Path):
    """워커에 캠페인 1건 등록 → 끝나면 정리."""
    cfg = tmp_path / "test.campaign.yaml"
    cfg.write_text("platform: naver\n", encoding="utf-8")

    cmp = Campaign(
        id="abc123",
        config_path=str(cfg),
        workspace=str(tmp_path),
        name="my campaign",
        status=Status.COMPLETED,
    )
    worker._campaigns[cmp.id] = cmp
    yield cmp
    worker._campaigns.pop(cmp.id, None)


def _write_report(campaign: Campaign, content: str = "- blog_id: b\n  keyword: 가경동 수학학원\n"):
    path = campaign.report_path()
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Campaign.report_path
# ---------------------------------------------------------------------------

class TestReportPath:

    def test_path_next_to_config(self, tmp_path: Path):
        cfg = tmp_path / "foo.yaml"
        cmp = Campaign(id="x", config_path=str(cfg), workspace=str(tmp_path))
        assert cmp.report_path() == tmp_path / "foo_report.yaml"

    def test_has_report_false_when_missing(self, tmp_path: Path):
        cfg = tmp_path / "foo.yaml"
        cmp = Campaign(id="x", config_path=str(cfg), workspace=str(tmp_path))
        assert cmp.to_dict()["has_report"] is False

    def test_has_report_true_when_present(self, tmp_path: Path):
        cfg = tmp_path / "foo.yaml"
        (tmp_path / "foo_report.yaml").write_text("[]", encoding="utf-8")
        cmp = Campaign(id="x", config_path=str(cfg), workspace=str(tmp_path))
        assert cmp.to_dict()["has_report"] is True


# ---------------------------------------------------------------------------
# GET /campaigns/<id>/report
# ---------------------------------------------------------------------------

class TestDownloadReport:

    def test_404_when_campaign_missing(self, client):
        res = client.get("/campaigns/nonexistent/report")
        assert res.status_code == 404
        assert res.get_json()["error"] == "not found"

    def test_409_when_still_running(self, client, campaign):
        campaign.status = Status.RUNNING
        res = client.get(f"/campaigns/{campaign.id}/report")
        assert res.status_code == 409

    def test_409_when_pending_sessions(self, client, campaign):
        campaign.status = Status.PENDING_SESSIONS
        res = client.get(f"/campaigns/{campaign.id}/report")
        assert res.status_code == 409

    def test_409_when_queued(self, client, campaign):
        campaign.status = Status.QUEUED
        res = client.get(f"/campaigns/{campaign.id}/report")
        assert res.status_code == 409

    def test_404_when_report_file_missing(self, client, campaign):
        # status 는 COMPLETED 지만 파일이 없는 경우
        res = client.get(f"/campaigns/{campaign.id}/report")
        assert res.status_code == 404
        assert res.get_json()["error"] == "report not found"

    def test_serves_file_when_completed(self, client, campaign):
        _write_report(campaign)
        res = client.get(f"/campaigns/{campaign.id}/report")
        assert res.status_code == 200
        assert "가경동 수학학원" in res.get_data(as_text=True)

    def test_attachment_filename_uses_campaign_name(self, client, campaign):
        _write_report(campaign)
        res = client.get(f"/campaigns/{campaign.id}/report")
        cd = res.headers.get("Content-Disposition", "")
        assert "attachment" in cd
        # campaign.name = "my campaign"
        assert "my campaign_report.yaml" in cd or "my%20campaign_report.yaml" in cd

    def test_attachment_falls_back_to_id_when_no_name(self, client, campaign):
        campaign.name = ""
        _write_report(campaign)
        res = client.get(f"/campaigns/{campaign.id}/report")
        cd = res.headers.get("Content-Disposition", "")
        assert f"{campaign.id}_report.yaml" in cd

    def test_serves_when_failed(self, client, campaign):
        campaign.status = Status.FAILED
        _write_report(campaign)
        res = client.get(f"/campaigns/{campaign.id}/report")
        assert res.status_code == 200

    def test_serves_when_cancelled(self, client, campaign):
        campaign.status = Status.CANCELLED
        _write_report(campaign)
        res = client.get(f"/campaigns/{campaign.id}/report")
        assert res.status_code == 200
