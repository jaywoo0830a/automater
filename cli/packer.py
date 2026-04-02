"""
cli/packer.py
--------------
캠페인 YAML + 관련 파일을 ZIP으로 패키징.

포함 대상:
    - 캠페인 YAML 파일
    - maps/ 디렉터리 (맵 YAML 파일들)
    - assets 디렉터리 (이미지, 폰트 등)
    - 세션 파일 (계정별 → sessions/ 하위로 배치)

Usage:
    from cli.packer import pack_campaign
    pack_campaign("campaign.yaml", "campaign.zip")
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

from cli.session_store import create_session_store


def pack_campaign(config_path: str, output_path: str | None = None) -> str:
    """캠페인 파일과 관련 리소스를 ZIP으로 패키징한다.

    Args:
        config_path: 캠페인 YAML 파일 경로.
        output_path: ZIP 출력 경로. None이면 {config_stem}.zip.

    Returns:
        생성된 ZIP 파일의 절대 경로.
    """
    config_file = Path(config_path).resolve()
    base_dir = config_file.parent

    if output_path is None:
        output_path = str(base_dir / f"{config_file.stem}.zip")

    output = Path(output_path).resolve()

    # YAML 파싱 (경로 수집용)
    import yaml
    raw = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}

    # 포함할 파일 수집
    files: list[tuple[Path, str]] = []  # (절대경로, ZIP 내 상대경로)

    # 1. 캠페인 YAML
    files.append((config_file, config_file.name))

    # 2. maps/ 디렉터리 내 파일
    maps_config = raw.get("maps") or {}
    for slug, entry in maps_config.items():
        if not isinstance(entry, dict):
            continue
        map_file = entry.get("file", "")
        if map_file:
            abs_path = _resolve(base_dir, map_file)
            if abs_path.exists():
                files.append((abs_path, map_file))

    # 3. assets 디렉터리
    assets_rel = raw.get("assets", "./assets")
    assets_dir = _resolve(base_dir, assets_rel)
    if assets_dir.is_dir():
        for child in assets_dir.rglob("*"):
            if child.is_file():
                rel = child.relative_to(base_dir)
                files.append((child, str(rel)))

    # 4. 세션 파일 — session_store에서 실제 경로를 찾아 sessions/ 하위로 배치
    _collect_sessions(raw, base_dir, files)

    # 중복 제거
    files = _deduplicate(files)

    # ZIP 생성
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for abs_path, arc_name in files:
            zf.write(abs_path, arc_name)

    return str(output)


def _collect_sessions(
    raw: dict[str, Any],
    base_dir: Path,
    files: list[tuple[Path, str]],
) -> None:
    """세션 파일을 찾아 files에 추가. ZIP 내 경로는 sessions/{filename}으로 통일."""
    accounts = raw.get("accounts") or []
    if not accounts:
        return

    # session_store 설정에서 실제 store 생성
    store_cfg = raw.get("session_store", "")
    store = create_session_store(store_cfg, base_dir=str(base_dir))

    for acc in accounts:
        username = acc.get("username", "")
        if not username:
            continue

        explicit = acc.get("session", "")
        abs_path: Path | None = None

        if explicit:
            # 명시적 session 경로
            candidate = _resolve(base_dir, explicit)
            if candidate.exists():
                abs_path = candidate
        else:
            # session_store 관례 경로 탐색
            from cli.session_store import FileSessionStore
            if isinstance(store, FileSessionStore):
                candidate = Path(store._key_to_path(username))
                if not candidate.is_absolute():
                    candidate = base_dir / candidate
                candidate = candidate.resolve()
                if candidate.exists():
                    abs_path = candidate

            # 추가 후보: base_dir 직하
            if not abs_path:
                candidate = base_dir / f"{username}_session.json"
                if candidate.exists():
                    abs_path = candidate

        if abs_path and abs_path.exists():
            arc_name = f"sessions/{abs_path.name}"
            if not _already_added(files, abs_path):
                files.append((abs_path, arc_name))


def _resolve(base_dir: Path, rel_path: str) -> Path:
    """base_dir 기준으로 상대 경로를 절대 경로로 변환."""
    p = Path(rel_path)
    if p.is_absolute():
        return p
    return (base_dir / p).resolve()


def _already_added(files: list[tuple[Path, str]], path: Path) -> bool:
    return any(f[0] == path for f in files)


def _deduplicate(files: list[tuple[Path, str]]) -> list[tuple[Path, str]]:
    seen: set[str] = set()
    result: list[tuple[Path, str]] = []
    for abs_path, arc_name in files:
        if arc_name not in seen:
            seen.add(arc_name)
            result.append((abs_path, arc_name))
    return result
