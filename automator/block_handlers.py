"""
automator/block_handlers.py
-----------------------------
BlockHandler ABC + concrete handlers + HANDLERS registry.

Naming convention: XxxBlock -> XxxHandler -> XxxStep

Adding a new Block type:
    1. Define the Block dataclass in options.py
    2. Define the PostStep subclass in editor.py (if new primitive needed)
    3. Write a BlockHandler subclass here
    4. Register it in HANDLERS
"""

from __future__ import annotations

import logging
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TYPE_CHECKING

logger = logging.getLogger(__name__)

from automator.editor import (
    PostStep,
    ParagraphStep,
    TextStep,
    ImageStep,
    FeaturedImageStep,
    HeadingStep,
    ListStep,
    QuoteStep,
    DividerStep,
    NewLineStep,
)
from automator.options import (
    Block,
    ParagraphBlock,
    TextBlock,
    ImageBlock,
    FeaturedImageBlock,
    HeadingBlock,
    ListBlock,
    QuoteBlock,
    DividerBlock,
    NewLineBlock,
    AiSectionBlock,
)
from automator.markdown_parser import parse_markdown, matches_structure

if TYPE_CHECKING:
    from automator.ports import TextGenerator, ImageProcessor


# ---------------------------------------------------------------------------
# ContentContext
# ---------------------------------------------------------------------------

@dataclass
class ContentContext:
    """Mutable context shared across handlers during content generation."""
    tmp_files: list[str]  = field(default_factory=list)
    text_gen:  Any        = None
    img_proc:  Any        = None


# ---------------------------------------------------------------------------
# BlockHandler ABC
# ---------------------------------------------------------------------------

class BlockHandler(ABC):
    """
    Converts a Block into PostStep(s).

    SRP: one handler = one block type's conversion rules.
    LSP: any handler is substitutable through to_steps().
    """

    @abstractmethod
    def to_steps(self, block: Block, ctx: ContentContext) -> list[PostStep]:
        """Convert block into PostStep(s)."""


# ---------------------------------------------------------------------------
# Concrete handlers
# ---------------------------------------------------------------------------

class ParagraphHandler(BlockHandler):
    """ParagraphBlock -> [ParagraphStep]"""

    def to_steps(self, block: ParagraphBlock, ctx: ContentContext) -> list[PostStep]:
        logger.info("[build]   AI 텍스트 생성 중... (프롬프트: %s)", block.prompt[:80])
        text = ctx.text_gen.generate(block.prompt)
        logger.info("[build]   AI 텍스트 생성 완료 (%d자)", len(text))
        return [ParagraphStep(text=text, newlines=block.newlines, wait_ms=block.wait_ms)]


class TextHandler(BlockHandler):
    """TextBlock -> [TextStep]. 인라인 텍스트 또는 파일 읽기 — AI 없음."""

    def to_steps(self, block: TextBlock, ctx: ContentContext) -> list[PostStep]:
        if block.file:
            # 파일 모드
            path = Path(block.file)
            if not path.exists():
                raise FileNotFoundError(f"Text file not found: {path}")
            raw = path.read_text(encoding="utf-8")

            if block.format == "html":
                text = raw
            else:
                text = self._plain_to_html(raw)

            return [TextStep(text=text, is_html=(block.format == "html"), wait_ms=block.wait_ms)]

        # 인라인 모드 — content를 그대로 삽입
        return [TextStep(text=block.content, is_html=False, wait_ms=block.wait_ms)]

    @staticmethod
    def _plain_to_html(raw: str) -> str:
        """빈 줄 기준 <p> 분리, 단일 줄바꿈은 <br>."""
        paragraphs = []
        for chunk in raw.split("\n\n"):
            chunk = chunk.strip()
            if chunk:
                inner = chunk.replace("\n", "<br>")
                paragraphs.append(f"<p>{inner}</p>")
        return "\n".join(paragraphs)


def _build_filename(role: str, keyword: str) -> str:
    """Build an upload filename from role and keyword."""
    if keyword:
        return f"{keyword}-{role}.jpg"
    return f"{role}.jpg"


def _save_temp(data: bytes, name: str, ctx: ContentContext) -> str:
    """Write data to a temp file and register it for cleanup."""
    tmp = tempfile.NamedTemporaryFile(
        suffix=".jpg", prefix=name.replace(".jpg", "_"), delete=False,
    )
    tmp.write(data)
    tmp.close()
    ctx.tmp_files.append(tmp.name)
    return tmp.name


def _describe_block(block: Any, label: str) -> str:
    """이미지 블록의 디버그 정보를 문자열로 만든다."""
    parts = [f"{label} 블록 정보:"]
    parts.append(f"  path = {getattr(block, 'path', None)!r}")

    link = getattr(block, "link", "")
    if link:
        parts.append(f"  link = {link!r}")

    kw = getattr(block, "filename_keyword", "")
    if kw:
        parts.append(f"  filename_keyword = {kw!r}")

    wait_ms = getattr(block, "wait_ms", 0)
    if wait_ms:
        parts.append(f"  wait_ms = {wait_ms}")

    # FeaturedImageBlock만 있는 필드들
    overlay = getattr(block, "overlay_text", "")
    if overlay:
        parts.append(f"  overlay_text = {overlay!r}")

    parts.append(f"  cwd = {Path.cwd()!s}")
    return "\n".join(parts)


def _validate_image_path(block: Any, label: str) -> Path:
    """이미지 블록의 경로를 검증하고 Path 객체를 반환한다.

    Raises:
        FileNotFoundError: 경로가 비어있거나, 존재하지 않거나, 파일이 아닌 경우.
            에러 메시지에 블록 정보(path/link/keyword/cwd)를 포함하여
            어느 블록의 어떤 설정이 문제인지 바로 알 수 있게 한다.
    """
    path = getattr(block, "path", "") or ""
    detail = _describe_block(block, label)

    if not path or not path.strip() or path.strip() == ".":
        raise FileNotFoundError(
            f"{label} 경로가 비어있거나 유효하지 않습니다: {path!r}\n"
            f"{detail}\n"
            f"→ YAML 캠페인 config에서 이 블록의 'path' 필드를 확인하세요. "
            f"GUI에서 저장했다면 이미지 블록 편집 다이얼로그를 다시 열어 파일을 재선택해주세요."
        )

    p = Path(path)

    if not p.exists():
        # 추가 힌트: 절대경로/상대경로 구분, 부모 디렉터리 존재 여부
        is_abs = p.is_absolute()
        parent_exists = p.parent.exists()
        hint_parts = [f"경로 타입: {'절대경로' if is_abs else '상대경로'}"]
        if not is_abs:
            hint_parts.append(f"해석된 절대경로: {p.resolve()!s}")
        hint_parts.append(f"부모 디렉터리 존재: {parent_exists}")
        if parent_exists:
            # 부모에 있는 파일 목록 일부 (최대 5개) 힌트
            try:
                siblings = sorted(s.name for s in p.parent.iterdir() if s.is_file())[:5]
                if siblings:
                    hint_parts.append(f"부모 디렉터리 내 파일 예시: {siblings}")
            except (OSError, PermissionError):
                pass

        raise FileNotFoundError(
            f"{label} 파일이 존재하지 않습니다: {path!r}\n"
            f"{detail}\n"
            f"  " + "\n  ".join(hint_parts) + "\n"
            f"→ 경로가 올바른지, assets 디렉터리 설정이 맞는지 확인하세요. "
            f"파일이 이동/삭제되었거나, 다른 사용자 환경(예: 윈도우↔WSL)의 경로일 수 있습니다."
        )

    if not p.is_file():
        raise FileNotFoundError(
            f"{label} 경로가 파일이 아닙니다 (디렉터리일 수 있음): {path!r}\n"
            f"{detail}\n"
            f"  is_dir = {p.is_dir()}\n"
            f"→ 디렉터리가 아닌 실제 이미지 파일 경로를 지정하세요."
        )

    return p


class ImageHandler(BlockHandler):
    """ImageBlock -> [ImageStep]"""

    def to_steps(self, block: ImageBlock, ctx: ContentContext) -> list[PostStep]:
        logger.info("[build]   이미지 경로: %r", block.path)
        p = _validate_image_path(block, "이미지")
        raw = p.read_bytes()
        logger.info("[build]   이미지 처리 중: %s (%.1fKB)", p.name, len(raw) / 1024)
        processed = ctx.img_proc.process(raw, block)
        name = _build_filename("preview", block.filename_keyword)
        path = _save_temp(processed, name, ctx)
        logger.info("[build]   이미지 처리 완료 → %s (%.1fKB)", Path(path).name, len(processed) / 1024)
        return [ImageStep(path=path, link=block.link, wait_ms=block.wait_ms)]


class FeaturedImageHandler(BlockHandler):
    """FeaturedImageBlock -> [FeaturedImageStep]"""

    def to_steps(self, block: FeaturedImageBlock, ctx: ContentContext) -> list[PostStep]:
        logger.info("[build]   대표이미지 경로: %r", block.path)
        p = _validate_image_path(block, "대표이미지")
        raw = p.read_bytes()
        logger.info("[build]   대표이미지 처리 중: %s (%.1fKB)", p.name, len(raw) / 1024)
        processed = ctx.img_proc.process(raw, block)
        name = _build_filename("featured", block.filename_keyword)
        path = _save_temp(processed, name, ctx)
        logger.info("[build]   대표이미지 처리 완료 → %s (%.1fKB)", Path(path).name, len(processed) / 1024)
        return [FeaturedImageStep(path=path, link=block.link, wait_ms=block.wait_ms)]


class HeadingHandler(BlockHandler):
    """HeadingBlock -> [HeadingStep]"""

    def to_steps(self, block: HeadingBlock, ctx: ContentContext) -> list[PostStep]:
        return [HeadingStep(level=block.level, text=block.text, wait_ms=block.wait_ms)]


class ListHandler(BlockHandler):
    """ListBlock -> [ListStep]"""

    def to_steps(self, block: ListBlock, ctx: ContentContext) -> list[PostStep]:
        if not block.items:
            return []
        return [ListStep(items=block.items, ordered=block.ordered, wait_ms=block.wait_ms)]


class QuoteHandler(BlockHandler):
    """QuoteBlock -> [QuoteStep]"""

    def to_steps(self, block: QuoteBlock, ctx: ContentContext) -> list[PostStep]:
        if not block.text:
            return []
        text = block.text
        if block.attribution:
            text += f"\n— {block.attribution}"
        return [QuoteStep(text=text, type=block.type, wait_ms=block.wait_ms)]


class DividerHandler(BlockHandler):
    """DividerBlock -> [DividerStep]"""

    def to_steps(self, block: DividerBlock, ctx: ContentContext) -> list[PostStep]:
        return [DividerStep(type=block.type, wait_ms=block.wait_ms)]


class NewLineHandler(BlockHandler):
    """NewLineBlock -> [NewLineStep]"""

    def to_steps(self, block: NewLineBlock, ctx: ContentContext) -> list[PostStep]:
        return [NewLineStep(count=block.count, wait_ms=block.wait_ms)]


# ---------------------------------------------------------------------------
# AiSection — 1회 호출로 마크다운 → 여러 블록
# ---------------------------------------------------------------------------

_STRUCTURE_HINTS = {
    "heading":   "## 소제목",
    "h1":        "# 대제목",
    "h2":        "## 소제목",
    "h3":        "### 소제목",
    "h4":        "#### 소제목",
    "h5":        "##### 소제목",
    "h6":        "###### 소제목",
    "list":      "- 글머리 기호 목록",
    "ordered_list": "1. 번호 목록",
    "quote":     "> 인용문",
    "divider":   "--- (구분선)",
    "paragraph": "일반 단락",
    "text":      "일반 단락",
}


def _build_ai_section_prompt(user_prompt: str, structure: tuple[str, ...]) -> str:
    """structure 가이드를 prompt 끝에 자연스럽게 추가."""
    hints = []
    for name in structure:
        hint = _STRUCTURE_HINTS.get(name.lower(), name)
        hints.append(f"- {hint}")

    if not hints:
        return user_prompt

    guide = (
        "\n\n다음 구조로 마크다운으로 작성해주세요. "
        "다른 텍스트는 추가하지 말고 본문만 작성하세요:\n"
        + "\n".join(hints)
    )
    return user_prompt + guide


class AiSectionHandler(BlockHandler):
    """AiSectionBlock -> 마크다운 파싱 결과의 여러 PostStep.

    1. AI를 1회 호출하여 마크다운 응답을 받음
    2. 마크다운을 Block 리스트로 파싱
    3. on_mismatch=strict면 structure와 시퀀스 일치 검증
    4. 각 Block을 해당 Handler로 위임하여 PostStep 생성
       (TextBlock으로 매핑된 단락은 추가 AI 호출 없이 그대로 삽입)
    """

    def to_steps(self, block: AiSectionBlock, ctx: ContentContext) -> list[PostStep]:
        if not block.prompt or not block.prompt.strip():
            raise ValueError("ai_section.prompt가 비어있습니다.")

        # 1. 프롬프트 조립
        if block.auto_prompt and block.structure:
            final_prompt = _build_ai_section_prompt(block.prompt, block.structure)
        else:
            final_prompt = block.prompt

        logger.info("[build]   ai_section AI 호출 중... (프롬프트: %s)", block.prompt[:80])

        # 2. AI 호출
        response = ctx.text_gen.generate(final_prompt)
        logger.info("[build]   ai_section AI 응답 수신 (%d자)", len(response))

        # 3. 마크다운 파싱
        parsed_blocks = parse_markdown(response)
        logger.info(
            "[build]   ai_section 파싱 완료 — %d개 블록: %s",
            len(parsed_blocks),
            [type(b).__name__ for b in parsed_blocks],
        )

        # 4. on_mismatch 검증
        if block.on_mismatch == "strict" and block.structure:
            if not matches_structure(parsed_blocks, block.structure):
                actual = [type(b).__name__ for b in parsed_blocks]
                raise ValueError(
                    f"ai_section: AI 응답이 structure와 일치하지 않습니다 (strict 모드).\n"
                    f"  expected: {list(block.structure)}\n"
                    f"  actual:   {actual}\n"
                    f"  raw response: {response[:200]!r}"
                )

        if not parsed_blocks:
            raise ValueError(
                f"ai_section: AI 응답에서 파싱된 블록이 없습니다. "
                f"raw response: {response[:200]!r}"
            )

        # 5. 각 블록을 해당 Handler로 변환 (재귀, 단 ai_section 자체는 제외)
        steps_out: list[PostStep] = []
        last_idx = len(parsed_blocks) - 1
        for i, parsed in enumerate(parsed_blocks):
            handler = get_handler(parsed)
            sub_steps = handler.to_steps(parsed, ctx)
            # 마지막 블록에만 ai_section의 wait_ms를 부여
            if i == last_idx and block.wait_ms > 0 and sub_steps:
                # 마지막 step의 wait_ms를 ai_section의 값으로 덮어쓴다
                last_step = sub_steps[-1]
                # PostStep은 frozen dataclass이므로 dataclasses.replace 사용
                from dataclasses import replace as _replace
                try:
                    sub_steps[-1] = _replace(last_step, wait_ms=block.wait_ms)
                except Exception:
                    pass
            steps_out.extend(sub_steps)

        return steps_out


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

HANDLERS: dict[type[Block], BlockHandler] = {
    ParagraphBlock:     ParagraphHandler(),
    TextBlock:          TextHandler(),
    ImageBlock:         ImageHandler(),
    FeaturedImageBlock: FeaturedImageHandler(),
    HeadingBlock:       HeadingHandler(),
    ListBlock:          ListHandler(),
    QuoteBlock:         QuoteHandler(),
    DividerBlock:       DividerHandler(),
    NewLineBlock:       NewLineHandler(),
    AiSectionBlock:     AiSectionHandler(),
}


def get_handler(block: Block) -> BlockHandler:
    """Look up the handler for a block. Raises KeyError if unregistered."""
    block_type = type(block)
    if block_type not in HANDLERS:
        raise KeyError(
            f"No BlockHandler registered for {block_type.__name__}. "
            f"Register one in HANDLERS."
        )
    return HANDLERS[block_type]
