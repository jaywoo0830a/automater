"""
api/app.py
-----------
Flask 앱 — 캠페인 업로드, 상태 조회, 로그 스트리밍.

실행:
    flask --app api.app run --host 0.0.0.0 --port 5000

환경변수:
    API_KEY  — 설정 시 X-API-Key 헤더 인증 활성화
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from flask import Flask, request, jsonify
from flask_sock import Sock

from api.auth import require_api_key
from api.workspace import create_workspace, remove_workspace, find_config
from api.worker import Worker, Status

app = Flask(__name__)
sock = Sock(app)
worker = Worker()


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@app.post("/campaigns")
@require_api_key
def upload_campaign():
    """ZIP 파일 업로드 → 캠페인 등록 및 실행."""
    if "file" not in request.files:
        return jsonify({"error": "file 필드가 필요합니다"}), 400

    file = request.files["file"]
    if not file.filename or not file.filename.endswith(".zip"):
        return jsonify({"error": ".zip 파일만 지원합니다"}), 400

    # 임시 파일로 저장 후 워크스페이스 생성
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        file.save(tmp)
        tmp_path = tmp.name

    try:
        campaign_id, workspace = create_workspace(tmp_path)
    except ValueError as exc:
        Path(tmp_path).unlink(missing_ok=True)
        return jsonify({"error": str(exc)}), 400
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    config_path = find_config(workspace)
    campaign = worker.submit(campaign_id, str(config_path), str(workspace))

    return jsonify({
        "id": campaign.id,
        "status": campaign.status.value,
        "config": str(config_path),
    }), 201


@app.get("/campaigns")
@require_api_key
def list_campaigns():
    """등록된 캠페인 목록."""
    campaigns = worker.list_all()
    return jsonify([c.to_dict() for c in campaigns])


@app.get("/campaigns/<campaign_id>")
@require_api_key
def get_campaign(campaign_id: str):
    """캠페인 상태 + 최근 로그."""
    campaign = worker.get(campaign_id)
    if not campaign:
        return jsonify({"error": "캠페인을 찾을 수 없습니다"}), 404

    data = campaign.to_dict()
    # 최근 50줄
    data["recent_logs"] = campaign.log_lines[-50:]
    return jsonify(data)


@app.delete("/campaigns/<campaign_id>")
@require_api_key
def cancel_campaign(campaign_id: str):
    """실행 중인 캠페인 중단."""
    campaign = worker.get(campaign_id)
    if not campaign:
        return jsonify({"error": "캠페인을 찾을 수 없습니다"}), 404

    if campaign.status not in (Status.QUEUED, Status.RUNNING):
        return jsonify({"error": "이미 종료된 캠페인입니다"}), 400

    worker.cancel(campaign_id)
    return jsonify({"id": campaign_id, "status": "cancelled"})


# ---------------------------------------------------------------------------
# WebSocket — 실시간 로그 스트리밍
# ---------------------------------------------------------------------------

@sock.route("/campaigns/<campaign_id>/logs")
def stream_logs(ws, campaign_id: str):
    """WebSocket으로 실시간 로그를 전송한다.

    연결 시 기존 로그를 모두 전송한 뒤, 이후 발생하는 로그를 실시간으로 push.
    캠페인이 종료되면 연결을 닫는다.
    """
    campaign = worker.get(campaign_id)
    if not campaign:
        ws.send("[error] 캠페인을 찾을 수 없습니다")
        ws.close()
        return

    # 기존 로그 전송
    for line in list(campaign.log_lines):
        ws.send(line)

    # 이미 종료된 경우
    if campaign.status not in (Status.QUEUED, Status.RUNNING):
        ws.send(f"[end] status={campaign.status.value}")
        ws.close()
        return

    # 실시간 스트리밍
    import queue
    q: queue.Queue[str] = queue.Queue()

    def on_line(line: str) -> None:
        q.put(line)

    campaign.add_listener(on_line)

    try:
        while campaign.status in (Status.QUEUED, Status.RUNNING):
            try:
                line = q.get(timeout=1.0)
                ws.send(line)
            except queue.Empty:
                continue
        # 남은 로그 flush
        while not q.empty():
            ws.send(q.get_nowait())
        ws.send(f"[end] status={campaign.status.value}")
    except Exception:
        pass
    finally:
        campaign.remove_listener(on_line)
