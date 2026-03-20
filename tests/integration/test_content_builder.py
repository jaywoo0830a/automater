"""
tests/integration/test_content_builder.py
--------------------------------------------
ContentBuilder.build() — block → step conversion pipeline.

Replaces: tests/test_block_handlers.py, tests/test_seo_integration.py
Uses injected StubTextGenerator and NoopImageProcessor — no mock.patch.
"""

import io
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from automator.contracts import PostingSpec
from automator.content_builder import ContentBuilder
from automator.editor import (
    ParagraphStep, ImageStep, FeaturedImageStep,
    HeadingStep, ListStep, QuoteStep,
)
from automator.stubs import StubTextGenerator, NoopImageProcessor
from automator.options import (
    AccountOption, TitleOption, PublishOption,
    ParagraphBlock, ImageBlock, FeaturedImageBlock,
    HeadingBlock, ListBlock, QuoteBlock, DividerBlock,
    Section,
)


def _account():
    return AccountOption(username="id", password="pw", meta={"blog_id": "b"})


def _spec(*blocks):
    return PostingSpec(
        account=_account(),
        title=TitleOption(fixed_title="T"),
        body=(Section(blocks=tuple(blocks)),) if blocks else (),
    )


@pytest.fixture
def builder():
    return ContentBuilder(StubTextGenerator(), NoopImageProcessor())


# ---------------------------------------------------------------------------
# Paragraph blocks
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_paragraph_block_generates_step(builder):
    post = builder.build(_spec(ParagraphBlock(prompt="test")))
    para_steps = [s for s in post.steps if isinstance(s, ParagraphStep)]
    assert len(para_steps) == 1
    assert para_steps[0].text  # non-empty stub text


@pytest.mark.unit
def test_multiple_paragraphs(builder):
    post = builder.build(_spec(
        ParagraphBlock(prompt="A"),
        ParagraphBlock(prompt="B"),
        ParagraphBlock(prompt="C"),
    ))
    para_steps = [s for s in post.steps if isinstance(s, ParagraphStep)]
    assert len(para_steps) == 3


# ---------------------------------------------------------------------------
# Heading / List / Quote / Divider
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_heading_block(builder):
    post = builder.build(_spec(HeadingBlock(level=2, text="Title")))
    assert any(isinstance(s, HeadingStep) and s.text == "Title" for s in post.steps)


@pytest.mark.unit
def test_list_block(builder):
    post = builder.build(_spec(ListBlock(items=("A", "B"), ordered=True)))
    assert any(isinstance(s, ListStep) for s in post.steps)


@pytest.mark.unit
def test_quote_block(builder):
    post = builder.build(_spec(QuoteBlock(text="wisdom", attribution="author")))
    assert any(isinstance(s, QuoteStep) for s in post.steps)


@pytest.mark.unit
def test_divider_block_produces_no_step(builder):
    post = builder.build(_spec(DividerBlock()))
    assert len(post.steps) == 0


# ---------------------------------------------------------------------------
# Image blocks (with real temp file)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_image_block_with_file(builder, tmp_path):
    img = tmp_path / "test.jpg"
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (100, 100), (200, 200, 200)).save(buf, format="JPEG")
    img.write_bytes(buf.getvalue())

    post = builder.build(_spec(ImageBlock(path=str(img))))
    img_steps = [s for s in post.steps if isinstance(s, ImageStep)]
    assert len(img_steps) == 1
    assert len(post.tmp_files) == 1


@pytest.mark.unit
def test_featured_image_marks_representative(builder, tmp_path):
    img = tmp_path / "feat.jpg"
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (100, 100), (200, 200, 200)).save(buf, format="JPEG")
    img.write_bytes(buf.getvalue())

    post = builder.build(_spec(FeaturedImageBlock(path=str(img))))
    feat_steps = [s for s in post.steps if isinstance(s, FeaturedImageStep)]
    assert len(feat_steps) == 1
    assert feat_steps[0].marks_representative is True


# ---------------------------------------------------------------------------
# SEO keyword integration
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_keyword_triggers_seo_prompt(builder):
    """ParagraphBlock with keyword uses build_prompt() internally."""
    post = builder.build(_spec(ParagraphBlock(keyword="강남 수학 과외")))
    para_steps = [s for s in post.steps if isinstance(s, ParagraphStep)]
    assert len(para_steps) == 1


# ---------------------------------------------------------------------------
# Empty body
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_empty_body_generates_stub(builder):
    post = builder.build(_spec())
    assert len(post.steps) == 1
    assert isinstance(post.steps[0], ParagraphStep)


# ---------------------------------------------------------------------------
# Title and schedule
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_title_in_post_content(builder):
    post = builder.build(_spec(ParagraphBlock(prompt="x")))
    assert post.title == "T"


@pytest.mark.unit
def test_immediate_schedule_is_none(builder):
    post = builder.build(_spec())
    assert post.schedule_at is None
