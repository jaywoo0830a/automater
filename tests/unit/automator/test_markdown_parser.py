"""
tests/unit/automator/test_markdown_parser.py
----------------------------------------------
parse_markdown() — 마크다운을 Block 리스트로 변환.
"""

import pytest

from automator.markdown_parser import parse_markdown, matches_structure
from automator.options import (
    HeadingBlock,
    ListBlock,
    QuoteBlock,
    DividerBlock,
    TextBlock,
)


# ---------------------------------------------------------------------------
# 빈 입력
# ---------------------------------------------------------------------------

class TestEmpty:

    def test_empty_string(self):
        assert parse_markdown("") == []

    def test_whitespace_only(self):
        assert parse_markdown("   \n\n  \t\n") == []


# ---------------------------------------------------------------------------
# 헤딩
# ---------------------------------------------------------------------------

class TestHeading:

    def test_h1(self):
        result = parse_markdown("# 대제목")
        assert len(result) == 1
        assert isinstance(result[0], HeadingBlock)
        assert result[0].level == 1
        assert result[0].text == "대제목"

    def test_h2(self):
        result = parse_markdown("## 소제목")
        assert result[0].level == 2

    def test_h6(self):
        result = parse_markdown("###### 작은 제목")
        assert result[0].level == 6

    def test_seven_hashes_not_heading(self):
        """7개 #는 헤딩이 아님 (마크다운 표준)."""
        result = parse_markdown("####### too many")
        assert isinstance(result[0], TextBlock)

    def test_multiple_headings(self):
        result = parse_markdown("# 제목1\n\n## 제목2\n\n### 제목3")
        assert len(result) == 3
        assert all(isinstance(b, HeadingBlock) for b in result)
        assert [b.level for b in result] == [1, 2, 3]


# ---------------------------------------------------------------------------
# 리스트
# ---------------------------------------------------------------------------

class TestUnorderedList:

    def test_dash(self):
        md = "- 항목1\n- 항목2\n- 항목3"
        result = parse_markdown(md)
        assert len(result) == 1
        assert isinstance(result[0], ListBlock)
        assert result[0].items == ("항목1", "항목2", "항목3")
        assert result[0].ordered is False

    def test_asterisk(self):
        md = "* a\n* b"
        result = parse_markdown(md)
        assert isinstance(result[0], ListBlock)
        assert result[0].items == ("a", "b")

    def test_plus(self):
        md = "+ x\n+ y"
        result = parse_markdown(md)
        assert isinstance(result[0], ListBlock)


class TestOrderedList:

    def test_basic(self):
        md = "1. 첫째\n2. 둘째\n3. 셋째"
        result = parse_markdown(md)
        assert len(result) == 1
        assert isinstance(result[0], ListBlock)
        assert result[0].items == ("첫째", "둘째", "셋째")
        assert result[0].ordered is True

    def test_two_separate_lists(self):
        """빈 줄로 분리된 두 리스트는 별개."""
        md = "- a\n- b\n\n- c\n- d"
        result = parse_markdown(md)
        assert len(result) == 2
        assert all(isinstance(b, ListBlock) for b in result)
        assert result[0].items == ("a", "b")
        assert result[1].items == ("c", "d")


# ---------------------------------------------------------------------------
# 인용구
# ---------------------------------------------------------------------------

class TestQuote:

    def test_single_line(self):
        result = parse_markdown("> 인생은 짧다")
        assert len(result) == 1
        assert isinstance(result[0], QuoteBlock)
        assert result[0].text == "인생은 짧다"

    def test_multi_line(self):
        md = "> 첫줄\n> 둘째줄"
        result = parse_markdown(md)
        assert len(result) == 1
        assert isinstance(result[0], QuoteBlock)
        assert "첫줄" in result[0].text
        assert "둘째줄" in result[0].text


# ---------------------------------------------------------------------------
# 구분선
# ---------------------------------------------------------------------------

class TestDivider:

    def test_dashes(self):
        result = parse_markdown("---")
        assert len(result) == 1
        assert isinstance(result[0], DividerBlock)

    def test_asterisks(self):
        result = parse_markdown("***")
        assert isinstance(result[0], DividerBlock)

    def test_underscores(self):
        result = parse_markdown("___")
        assert isinstance(result[0], DividerBlock)


# ---------------------------------------------------------------------------
# 일반 텍스트
# ---------------------------------------------------------------------------

class TestText:

    def test_single_line(self):
        result = parse_markdown("이것은 일반 텍스트입니다.")
        assert len(result) == 1
        assert isinstance(result[0], TextBlock)
        assert result[0].content == "이것은 일반 텍스트입니다."

    def test_multi_line_paragraph(self):
        """빈 줄 없이 이어진 줄은 하나의 TextBlock."""
        md = "첫 줄\n둘째 줄\n셋째 줄"
        result = parse_markdown(md)
        assert len(result) == 1
        assert isinstance(result[0], TextBlock)
        assert "첫 줄" in result[0].content
        assert "둘째 줄" in result[0].content
        assert "셋째 줄" in result[0].content

    def test_separated_paragraphs(self):
        md = "첫 단락\n\n둘째 단락"
        result = parse_markdown(md)
        assert len(result) == 2
        assert all(isinstance(b, TextBlock) for b in result)


# ---------------------------------------------------------------------------
# 복합 케이스
# ---------------------------------------------------------------------------

class TestMixed:

    def test_full_document(self):
        md = """## 수학학원의 장점

- 맞춤 케어
- 체계적 커리큘럼
- 우수한 강사진

학원 선택은 자녀의 성적에 큰 영향을 미칩니다.

> 교육은 미래를 여는 열쇠다

---

마무리 단락입니다."""
        result = parse_markdown(md)
        types = [type(b).__name__ for b in result]
        assert types == [
            "HeadingBlock",
            "ListBlock",
            "TextBlock",
            "QuoteBlock",
            "DividerBlock",
            "TextBlock",
        ]
        assert result[0].level == 2
        assert result[1].items == ("맞춤 케어", "체계적 커리큘럼", "우수한 강사진")

    def test_user_actual_response(self):
        """현실적인 AI 응답 패턴."""
        md = """## 5가지 장점

1. 맞춤 케어
2. 체계적
3. 강사진

이런 이유로 학원이 중요합니다."""
        result = parse_markdown(md)
        assert len(result) == 3
        assert isinstance(result[0], HeadingBlock)
        assert isinstance(result[1], ListBlock)
        assert result[1].ordered is True
        assert isinstance(result[2], TextBlock)


# ---------------------------------------------------------------------------
# matches_structure
# ---------------------------------------------------------------------------

class TestMatchesStructure:

    def test_exact_match(self):
        blocks = parse_markdown("## 제목\n\n- a\n- b\n\n본문입니다.")
        assert matches_structure(blocks, ["heading", "list", "paragraph"])

    def test_h2_alias(self):
        blocks = parse_markdown("## 제목")
        assert matches_structure(blocks, ["h2"])

    def test_text_alias(self):
        blocks = parse_markdown("일반 텍스트")
        assert matches_structure(blocks, ["text"])

    def test_length_mismatch(self):
        blocks = parse_markdown("## 제목\n\n- a\n- b")
        assert not matches_structure(blocks, ["heading", "list", "paragraph"])

    def test_type_mismatch(self):
        blocks = parse_markdown("## 제목\n\n본문")
        assert not matches_structure(blocks, ["heading", "list"])

    def test_unknown_structure_name(self):
        blocks = parse_markdown("## x")
        assert not matches_structure(blocks, ["unknown"])
