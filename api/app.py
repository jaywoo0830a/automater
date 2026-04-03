"""
api/app.py
-----------
Flask app.

Endpoints:
    POST   /campaigns                    ZIP upload -> register
    GET    /campaigns                    list
    GET    /campaigns/{id}               status + logs
    POST   /campaigns/{id}/execute       start execution
    GET    /campaigns/{id}/sessions      session status per account
    POST   /campaigns/{id}/sessions/vnc  VNC login for a campaign account
    DELETE /campaigns/{id}               cancel

    POST   /sessions/vnc                 standalone VNC login
    GET    /sessions/vnc/{id}            VNC session status
    DELETE /sessions/vnc/{id}            VNC session stop

    WS     /campaigns/{id}/logs          realtime log stream
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from flask import Flask, request, jsonify
from flask_sock import Sock

from api.auth import require_api_key
from api.workspace import create_workspace, remove_workspace, find_config
from api.worker import Worker, Status, check_sessions, parse_campaign_accounts
from api.vnc_session import create_vnc_session, get_vnc_session, delete_vnc_session

app = Flask(__name__)
sock = Sock(app)
worker = Worker()


# ---------------------------------------------------------------------------
# Campaigns — upload, list, status, execute, cancel
# ---------------------------------------------------------------------------

@app.post("/campaigns")
@require_api_key
def upload_campaign():
    """ZIP upload -> register campaign (pending_sessions)."""
    if "file" not in request.files:
        return jsonify({"error": "file field required"}), 400

    file = request.files["file"]
    if not file.filename or not file.filename.endswith(".zip"):
        return jsonify({"error": ".zip only"}), 400

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

    config_path = find_config(workspace).resolve()
    name = request.form.get("name", "") or Path(file.filename).stem
    campaign = worker.register(campaign_id, str(config_path), str(workspace.resolve()), name=name)

    sessions = check_sessions(str(config_path), str(workspace.resolve()))

    # 세션이 모두 준비되어 있으면 바로 실행
    if sessions["all_ready"]:
        worker.execute(campaign_id)

    return jsonify({
        "id": campaign.id,
        "status": campaign.status.value,
        "sessions": sessions,
    }), 201


@app.get("/campaigns")
@require_api_key
def list_campaigns():
    campaigns = worker.list_all()
    return jsonify([c.to_dict() for c in campaigns])


@app.get("/campaigns/<campaign_id>")
@require_api_key
def get_campaign(campaign_id: str):
    campaign = worker.get(campaign_id)
    if not campaign:
        return jsonify({"error": "not found"}), 404

    data = campaign.to_dict()
    data["logs"] = campaign.log_lines
    return jsonify(data)


@app.post("/campaigns/<campaign_id>/execute")
@require_api_key
def execute_campaign(campaign_id: str):
    """세션 준비 완료 후 캠페인 실행."""
    campaign = worker.get(campaign_id)
    if not campaign:
        return jsonify({"error": "not found"}), 404

    if campaign.status != Status.PENDING_SESSIONS:
        return jsonify({"error": f"cannot execute: status={campaign.status.value}"}), 400

    sessions = check_sessions(campaign.config_path, campaign.workspace, validate=False)
    if not sessions["all_ready"]:
        missing = [a["username"] for a in sessions["accounts"] if not a["has_session"]]
        return jsonify({"error": "sessions not ready", "missing": missing}), 400

    worker.execute(campaign_id)
    return jsonify({"id": campaign_id, "status": "queued"})


@app.get("/campaigns/<campaign_id>/sessions")
@require_api_key
def get_campaign_sessions(campaign_id: str):
    """캠페인 내 각 계정의 세션 상태."""
    campaign = worker.get(campaign_id)
    if not campaign:
        return jsonify({"error": "not found"}), 404

    return jsonify(check_sessions(campaign.config_path, campaign.workspace, validate=False))


@app.post("/campaigns/<campaign_id>/sessions/vnc")
@require_api_key
def start_campaign_vnc(campaign_id: str):
    """캠페인 계정의 VNC 로그인 세션 시작."""
    campaign = worker.get(campaign_id)
    if not campaign:
        return jsonify({"error": "campaign not found"}), 404

    data = request.get_json(silent=True) or {}
    target_username = data.get("username", "")
    if not target_username:
        return jsonify({"error": "username required"}), 400

    # YAML에서 계정 정보 조회
    accounts = parse_campaign_accounts(campaign.config_path)
    account = None
    for acc in accounts:
        if acc.get("username") == target_username:
            account = acc
            break

    if not account:
        return jsonify({"error": f"account '{target_username}' not found in campaign"}), 404

    # 세션 저장 경로 = 워크스페이스 sessions/
    sessions_dir = str(Path(campaign.workspace) / "sessions")
    config = {
        "session_store": "file",
        "_base_dir": sessions_dir,
    }

    session = create_vnc_session(account, config)
    return jsonify(session.to_dict()), 201


@app.delete("/campaigns/<campaign_id>")
@require_api_key
def cancel_campaign(campaign_id: str):
    campaign = worker.get(campaign_id)
    if not campaign:
        return jsonify({"error": "not found"}), 404

    if campaign.status in (Status.QUEUED, Status.RUNNING):
        worker.cancel(campaign_id)
    return jsonify({"id": campaign_id, "status": "cancelled"})


# ---------------------------------------------------------------------------
# VNC session status/stop (used by frontend polling)
# ---------------------------------------------------------------------------

@app.get("/sessions/vnc/<session_id>")
@require_api_key
def get_vnc(session_id: str):
    session = get_vnc_session(session_id)
    if not session:
        return jsonify({"error": "not found"}), 404
    return jsonify(session.to_dict())


@app.delete("/sessions/vnc/<session_id>")
@require_api_key
def stop_vnc(session_id: str):
    if delete_vnc_session(session_id):
        return jsonify({"session_id": session_id, "status": "closed"})
    return jsonify({"error": "not found"}), 404


# ---------------------------------------------------------------------------
# WebSocket — realtime log stream
# ---------------------------------------------------------------------------

@sock.route("/campaigns/<campaign_id>/logs")
def stream_logs(ws, campaign_id: str):
    campaign = worker.get(campaign_id)
    if not campaign:
        ws.send("[error] not found")
        return

    for line in list(campaign.log_lines):
        ws.send(line)

    if campaign.status not in (Status.QUEUED, Status.RUNNING):
        ws.send(f"[end] status={campaign.status.value}")
        return

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
        while not q.empty():
            ws.send(q.get_nowait())
        ws.send(f"[end] status={campaign.status.value}")
    except Exception:
        pass
    finally:
        campaign.remove_listener(on_line)
