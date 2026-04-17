"""
cli/packer.py
--------------
캠페인 YAML + 관련 파일을 ZIP으로 패키징.

포함 대상:
    - 캠페인 YAML 파일
    - maps/ 디렉터리 (맵 YAML 파일들)
    - assets 디렉터리 (이미지, 폰트 등)

세션 파일은 포함하지 않는다. 패키지를 받는 머신에서 자체적으로 로그인해
세션을 새로 만드는 구조이기 때문.

Usage:
    from cli.packer import pack_campaign
    pack_campaign("campaign.yaml", "campaign.zip")
"""

from __future__ import annotations

import zipfile
from pathlib import Path


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

    # 세션 파일 제거 — 서버에서 직접 로그인해야 함
    files = _exclude_sessions(files, raw)

    # 중복 제거
    files = _deduplicate(files)

    # YAML에서 session 경로 제거 후 패키징
    cleaned_yaml = _strip_session_paths(raw)
    config_bytes = yaml.dump(
        cleaned_yaml, allow_unicode=True,
        default_flow_style=False, sort_keys=False,
    ).encode("utf-8")

    # ZIP 생성
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        # 캠페인 YAML은 세션 경로가 제거된 버전으로 저장
        zf.writestr(config_file.name, config_bytes)
        for abs_path, arc_name in files:
            if arc_name == config_file.name:
                continue  # 이미 위에서 저장함
            zf.write(abs_path, arc_name)

    return str(output)


def _resolve(base_dir: Path, rel_path: str) -> Path:
    """base_dir 기준으로 상대 경로를 절대 경로로 변환."""
    p = Path(rel_path)
    if p.is_absolute():
        return p
    return (base_dir / p).resolve()


def _deduplicate(files: list[tuple[Path, str]]) -> list[tuple[Path, str]]:
    seen: set[str] = set()
    result: list[tuple[Path, str]] = []
    for abs_path, arc_name in files:
        if arc_name not in seen:
            seen.add(arc_name)
            result.append((abs_path, arc_name))
    return result


def _exclude_sessions(
    files: list[tuple[Path, str]], raw: dict,
) -> list[tuple[Path, str]]:
    """Remove session files from the file list."""
    session_names: set[str] = set()
    for acc in raw.get("accounts", []):
        s = acc.get("session", "")
        if s:
            session_names.add(Path(s).name)
            session_names.add(Path(s).stem)

    # Also exclude any *_session.json pattern
    def is_session(arc_name: str) -> bool:
        name = Path(arc_name).name
        if name in session_names:
            return True
        if name.endswith("_session.json"):
            return True
        if name == "session_state.json":
            return True
        return False

    return [(p, a) for p, a in files if not is_session(a)]


def _strip_session_paths(raw: dict) -> dict:
    """Return a copy of the config with session paths removed from accounts."""
    import copy
    cleaned = copy.deepcopy(raw)
    for acc in cleaned.get("accounts", []):
        acc.pop("session", None)
    # Also remove session_store if it's file-based
    ss = cleaned.get("session_store", "")
    if ss and ss not in ("redis", "rediss") and "://" not in str(ss):
        cleaned.pop("session_store", None)
    return cleaned
