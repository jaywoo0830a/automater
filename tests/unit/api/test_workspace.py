"""
tests/unit/api/test_workspace.py
----------------------------------
ZIP 업로드 → 워크스페이스 해제 로직 검증.

두 가지 정상 케이스를 반드시 지원해야 한다:
    1. CLI pack 이 만든 ZIP — YAML 이 ZIP 루트에 평탄하게 들어있음.
    2. 사용자가 workspace 폴더를 통째로 ZIP 한 경우 — YAML 이 한 겹 서브디렉토리 안.

두 경우 모두 반환된 workspace 루트와 YAML 의 부모 디렉토리가 일치해야 한다.
그렇지 않으면 check_sessions / VNC 세션 저장 / _patch_config 가 서로 다른 루트를 보게 돼
세션·에셋을 못 찾는 버그가 발생한다.
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

import pytest

from api.workspace import create_workspace, remove_workspace, find_config, WORKSPACES_DIR


_MIN_YAML = (
    "platform: naver\n"
    "accounts:\n"
    "  - username: u1\n"
    "    blog_id: u1\n"
    "titles:\n"
    "  main: [hello]\n"
    "keywords: {}\n"
    "publish:\n"
    "  schedule: now\n"
)


@pytest.fixture
def chdir_tmp(tmp_path, monkeypatch):
    """WORKSPACES_DIR 이 'workspaces' 상대경로라서 cwd 를 tmp 로 옮긴다."""
    monkeypatch.chdir(tmp_path)
    yield tmp_path


def _make_zip(zip_path: Path, entries: dict[str, str]) -> None:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for arc_name, content in entries.items():
            zf.writestr(arc_name, content)


# ---------------------------------------------------------------------------
# 정상 케이스
# ---------------------------------------------------------------------------

def test_flat_zip_yaml_at_root(chdir_tmp):
    """CLI pack 이 만드는 형태 — YAML 이 ZIP 루트에 있는 경우."""
    zip_path = chdir_tmp / "flat.zip"
    _make_zip(zip_path, {
        "campaign.yaml": _MIN_YAML,
        "assets/img.txt": "x",
    })

    campaign_id, workspace = create_workspace(zip_path)

    config = find_config(workspace)
    assert config is not None
    assert config.parent.resolve() == workspace.resolve()
    assert (workspace / "assets" / "img.txt").exists()


def test_nested_zip_yaml_in_subdir(chdir_tmp):
    """사용자가 workspace 폴더를 통째로 묶은 형태 — YAML 이 서브디렉토리 안."""
    zip_path = chdir_tmp / "nested.zip"
    _make_zip(zip_path, {
        "my_campaign/campaign.yaml": _MIN_YAML,
        "my_campaign/assets/img.txt": "x",
    })

    campaign_id, workspace = create_workspace(zip_path)

    # 버그 재발 방지의 핵심 단언:
    # workspace 루트와 YAML 부모가 반드시 동일해야 한다.
    config = find_config(workspace)
    assert config is not None
    assert config.parent.resolve() == workspace.resolve(), (
        "workspace 루트가 YAML 부모와 달라 check_sessions / _patch_config 가 "
        "서로 다른 디렉토리를 바라보게 된다 (세션·에셋을 못 찾는 버그)"
    )
    # 에셋도 새 루트 기준으로 접근 가능해야 함
    assert (workspace / "assets" / "img.txt").exists()


# ---------------------------------------------------------------------------
# 에러 케이스
# ---------------------------------------------------------------------------

def test_invalid_zip_raises(chdir_tmp):
    bad = chdir_tmp / "bad.zip"
    bad.write_bytes(b"not a zip")
    with pytest.raises(ValueError):
        create_workspace(bad)


def test_zip_without_yaml_raises_and_cleans_up(chdir_tmp):
    zip_path = chdir_tmp / "noyaml.zip"
    _make_zip(zip_path, {"readme.txt": "hi"})

    with pytest.raises(ValueError):
        create_workspace(zip_path)

    # 실패 시 orphan 워크스페이스가 남으면 안 된다
    if WORKSPACES_DIR.exists():
        assert list(WORKSPACES_DIR.iterdir()) == []


# ---------------------------------------------------------------------------
# remove_workspace
# ---------------------------------------------------------------------------

def test_remove_workspace_removes_entire_campaign_id_dir(chdir_tmp):
    zip_path = chdir_tmp / "x.zip"
    _make_zip(zip_path, {"ws/campaign.yaml": _MIN_YAML})

    campaign_id, workspace = create_workspace(zip_path)
    assert (WORKSPACES_DIR / campaign_id).exists()

    remove_workspace(campaign_id)

    # 서브디렉토리를 workspace 로 재지정한 경우에도 campaign_id 디렉토리 전체가 지워져야 한다.
    assert not (WORKSPACES_DIR / campaign_id).exists()
