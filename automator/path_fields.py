"""캠페인 잡 딕셔너리 내 경로 필드 레지스트리.

GUI 패키징 다이얼로그에서 절대경로를 찾아내 상대화/복사하는 데 사용.

경로 필드 목록:
    post[*].image.path            (asset)
    post[*].featured_image.path   (asset)
    post[*].text.file             (asset)
    maps.<slug>.file              (asset)
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Literal

Kind = Literal["asset"]

_TOKEN_RE = re.compile(r"\{[^}]+\}")


@dataclass
class PathField:
    """잡 딕셔너리의 한 경로 필드를 가리키는 핸들."""

    location: str
    value: str
    kind: Kind
    setter: Callable[[str], None]

    @property
    def is_template(self) -> bool:
        """`{map:photo}` 같은 토큰이 포함된 값은 실제 파일 경로가 아님."""
        return bool(_TOKEN_RE.search(self.value))

    @property
    def is_absolute(self) -> bool:
        if not self.value or self.is_template:
            return False
        try:
            return Path(self.value).is_absolute()
        except (OSError, ValueError):
            return False

    @property
    def is_relative(self) -> bool:
        return bool(self.value) and not self.is_template and not self.is_absolute


def iter_path_fields(job: dict) -> Iterator[PathField]:
    """잡 딕셔너리 내의 모든 경로성 필드를 순회한다.

    setter는 입력 ``job`` 딕셔너리를 그대로 변경하므로, 원본을 보존하려면
    호출 전에 deepcopy 할 것.
    """
    # post blocks
    for i, block in enumerate(job.get("post") or []):
        if not isinstance(block, dict):
            continue
        for key in ("image", "featured_image"):
            val = block.get(key)
            if isinstance(val, dict) and "path" in val:
                yield PathField(
                    location=f"post[{i}].{key}.path",
                    value=str(val.get("path") or ""),
                    kind="asset",
                    setter=_setter(val, "path"),
                )
        text_val = block.get("text")
        if isinstance(text_val, dict) and "file" in text_val:
            yield PathField(
                location=f"post[{i}].text.file",
                value=str(text_val.get("file") or ""),
                kind="asset",
                setter=_setter(text_val, "file"),
            )

    # maps.<slug>.file
    maps = job.get("maps")
    if isinstance(maps, dict):
        for slug, entry in maps.items():
            if isinstance(entry, dict) and "file" in entry:
                yield PathField(
                    location=f"maps.{slug}.file",
                    value=str(entry.get("file") or ""),
                    kind="asset",
                    setter=_setter(entry, "file"),
                )


def relocate_to(field: PathField, target_dir: Path) -> tuple[str, bool]:
    """절대경로 필드를 ``target_dir`` 안으로 복사(필요 시)하고 상대경로로 변환.

    Returns:
        (new_relative_path, was_copied)
        ``new_relative_path``는 ``target_dir``에 대한 상대경로.

    Raises:
        ValueError: 값이 빈 문자열, 토큰, 또는 상대경로인 경우.
        FileNotFoundError: 원본 파일이 존재하지 않는 경우.
    """
    if not field.value:
        raise ValueError("빈 값은 처리할 수 없습니다")
    if field.is_template:
        raise ValueError("토큰 값은 처리할 수 없습니다")
    if not field.is_absolute:
        raise ValueError("이미 상대경로입니다")

    src = Path(field.value)
    if not src.exists():
        raise FileNotFoundError(str(src))

    target = target_dir.resolve()
    src_resolved = src.resolve()

    # target 안에 이미 있으면 상대화만
    try:
        rel = src_resolved.relative_to(target)
        return str(rel), False
    except ValueError:
        pass

    # target 밖이면 복사 (이름 충돌 시 suffix 증분)
    target.mkdir(parents=True, exist_ok=True)
    dest = target / src.name
    n = 1
    while dest.exists():
        dest = target / f"{src.stem}_{n}{src.suffix}"
        n += 1
    shutil.copy2(src, dest)
    return dest.name, True


def _setter(container: dict, key: str) -> Callable[[str], None]:
    def _set(new_value: str) -> None:
        container[key] = new_value

    return _set
