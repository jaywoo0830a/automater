"""
tests/unit/automator/test_post_preview.py
--------------------------------------------
Unit tests for preview_post — dry-run post generation.

Preview shows what a post would look like with a given template
and keywords, without calling Gemini or processing real images.
"""

import pytest

from automator.post_preview import preview_post, PostPreview, BlockPreview
from automator.options import (
    TitleOption,
    Section,
    HeadingBlock,
    ParagraphBlock,
    ImageBlock,
    FeaturedImageBlock,
    ListBlock,
    QuoteBlock,
    DividerBlock,
)


class TestPreviewPost:

    def test_generates_sample_title(self):
        title = TitleOption(
            template="{keyword:region} {keyword:subject}",
            values={"region": "강남", "subject": "수학"},
        )
        sections = (Section(blocks=(ParagraphBlock(prompt="강남 수학 과외를 소개해줘"),)),)
        result = preview_post(title, sections)

        assert result.sample_title == "강남 수학"

    def test_generates_sample_title_with_fixed_title(self):
        title = "고정 제목"
        sections = (Section(blocks=(ParagraphBlock(),)),)
        result = preview_post(title, sections)

        assert result.sample_title == "고정 제목"

    def test_paragraph_block_shows_prompt_placeholder(self):
        title = "제목"
        sections = (Section(blocks=(
            ParagraphBlock(prompt="강남 수학 과외 소개"),
        )),)
        result = preview_post(title, sections)

        assert len(result.blocks) == 1
        assert result.blocks[0].block_type == "paragraph"
        assert "강남 수학 과외 소개" in result.blocks[0].placeholder

    def test_paragraph_block_with_prompt_shows_prompt(self):
        title = "제목"
        sections = (Section(blocks=(
            ParagraphBlock(prompt="Write about SEO benefits"),
        )),)
        result = preview_post(title, sections)

        assert "SEO benefits" in result.blocks[0].placeholder

    def test_paragraph_block_empty_shows_generic(self):
        title = "제목"
        sections = (Section(blocks=(ParagraphBlock(),)),)
        result = preview_post(title, sections)

        assert result.blocks[0].block_type == "paragraph"
        assert result.blocks[0].placeholder  # not empty

    def test_heading_block_shows_text(self):
        title = "제목"
        sections = (Section(blocks=(HeadingBlock(level=2, text="소제목"),)),)
        result = preview_post(title, sections)

        assert result.blocks[0].block_type == "heading"
        assert "소제목" in result.blocks[0].placeholder

    def test_image_block_shows_path(self):
        title = "제목"
        sections = (Section(blocks=(
            ImageBlock(path="/images/sample.jpg"),
        )),)
        result = preview_post(title, sections)

        assert result.blocks[0].block_type == "image"
        assert "sample.jpg" in result.blocks[0].placeholder

    def test_featured_image_block(self):
        title = "제목"
        sections = (Section(blocks=(
            FeaturedImageBlock(path="/images/thumb.jpg", overlay_text="강남 수학"),
        )),)
        result = preview_post(title, sections)

        assert result.blocks[0].block_type == "featured"
        assert "thumb.jpg" in result.blocks[0].placeholder

    def test_list_block(self):
        title = "제목"
        sections = (Section(blocks=(
            ListBlock(items=("항목1", "항목2", "항목3"), ordered=True),
        )),)
        result = preview_post(title, sections)

        assert result.blocks[0].block_type == "list"
        assert "3 items" in result.blocks[0].placeholder

    def test_quote_block(self):
        title = "제목"
        sections = (Section(blocks=(
            QuoteBlock(text="인용문 텍스트", attribution="출처"),
        )),)
        result = preview_post(title, sections)

        assert result.blocks[0].block_type == "quote"
        assert "출처" in result.blocks[0].placeholder

    def test_divider_block(self):
        title = "제목"
        sections = (Section(blocks=(DividerBlock(),)),)
        result = preview_post(title, sections)

        assert result.blocks[0].block_type == "divider"

    def test_multiple_sections_flattened(self):
        title = "제목"
        sections = (
            Section(blocks=(
                HeadingBlock(level=2, text="서론"),
                ParagraphBlock(prompt="강남 과외"),
            )),
            Section(blocks=(
                ParagraphBlock(prompt="수학 과외"),
                ImageBlock(path="/img/a.jpg"),
            )),
        )
        result = preview_post(title, sections)

        assert len(result.blocks) == 4
        types = [b.block_type for b in result.blocks]
        assert types == ["heading", "paragraph", "paragraph", "image"]

    def test_empty_sections_returns_empty_blocks(self):
        title = "제목"
        result = preview_post(title, ())

        assert result.sample_title == "제목"
        assert result.blocks == []

    def test_block_order_matches_section_order(self):
        title = "제목"
        sections = (Section(blocks=(
            HeadingBlock(level=2, text="H2"),
            ParagraphBlock(prompt="KW 프롬프트"),
            ImageBlock(path="/x.jpg"),
            ParagraphBlock(prompt="P2"),
            FeaturedImageBlock(path="/thumb.jpg"),
        )),)
        result = preview_post(title, sections)

        assert [b.block_type for b in result.blocks] == [
            "heading", "paragraph", "image", "paragraph", "featured",
        ]
