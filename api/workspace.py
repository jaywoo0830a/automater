"""
api/workspace.py
-----------------
캠페인 워크스페이스 관리.

업로드된 ZIP을 해제하고, 워크스페이스 경로를 반환한다.
구조: workspaces/{campaign_id}/
"""

from __future__ import annotations

import shutil
import uuid
import zipfile
from pathlib import Path

WORKSPACES_DIR = Path("workspaces")


def create_workspace(zip_path: str | Path) -> tuple[str, Path]:
    """ZIP 파일을 해제하여 워크스페이스를 생성한다.

    Returns:
        (campaign_id, workspace_path)

    Raises:
        ValueError: ZIP이 아니거나 YAML 파일이 없는 경우.
    """
    zip_path = Path(zip_path)

    if not zipfile.is_zipfile(zip_path):
        raise ValueError("유효한 ZIP 파일이 아닙니다")

    campaign_id = uuid.uuid4().hex[:12]
    workspace = WORKSPACES_DIR / campaign_id
    workspace.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(workspace)

    # YAML 파일 찾기
    config_file = find_config(workspace)
    if not config_file:
        shutil.rmtree(workspace, ignore_errors=True)
        raise ValueError("ZIP 내에 YAML 캠페인 파일이 없습니다")

    return campaign_id, workspace


def find_config(workspace: Path) -> Path | None:
    """워크스페이스에서 캠페인 YAML 파일을 찾는다."""
    for pattern in ("*.yaml", "*.yml"):
        files = list(workspace.glob(pattern))
        # campaign.yaml / *.campaign.yaml 우선
        for f in files:
            if "campaign" in f.stem:
                return f
        if files:
            return files[0]

    # 서브디렉터리 한 단계까지 탐색 (ZIP 내 폴더 구조)
    for child in workspace.iterdir():
        if child.is_dir():
            result = find_config(child)
            if result:
                return result

    return None


def remove_workspace(campaign_id: str) -> None:
    """워크스페이스를 삭제한다."""
    workspace = WORKSPACES_DIR / campaign_id
    if workspace.exists():
        shutil.rmtree(workspace, ignore_errors=True)


def list_workspaces() -> list[str]:
    """존재하는 워크스페이스 ID 목록을 반환한다."""
    if not WORKSPACES_DIR.exists():
        return []
    return [d.name for d in WORKSPACES_DIR.iterdir() if d.is_dir()]
