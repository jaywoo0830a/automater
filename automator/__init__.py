"""
automator
---------
Blog automation package.

Public interface
----------------
    PostingJob          — builder + orchestrator (entry point)
    BlogEditor          — abstract editor with 7 primitives
    SmartEditorOne      — Naver Smart Editor implementation

    AccountOption, TitleOption, PublishOption, RunSetting — config
    Section, Block types (7)    — post body structure
    BlockHandler, HANDLERS      — extension point for new block types

    generate_title()            — TitleOption -> str
    generate_paragraphs()       — prompt -> list[str]
    validate_template()         — raises ValueError on bad template

Usage
-----
    job = (
        PostingJob
        .for_account(AccountOption(username="id", password="pw"))
        .with_title(TitleOption(fixed_title="제목"))
        .with_body([Section(blocks=(ParagraphBlock(),))])
        .with_publish(PublishOption(mode="immediate"))
    )
    job.run(editor)
"""

from automator.options import (
    AccountOption,
    TitleOption,
    Section,
    Block,
    HeadingBlock,
    ParagraphBlock,
    ImageBlock,
    FeaturedImageBlock,
    ListBlock,
    QuoteBlock,
    DividerBlock,
    PublishOption,
    RunSetting,
)
from automator.editor import BlogEditor
from automator.title_generator import generate_title, validate_template
from automator.paragraph_generator import generate_paragraphs, RateLimitError
from automator.block_handlers import BlockHandler, ContentContext, get_handler, HANDLERS
from automator.browser_actions import (
    click_if_visible, click_polling,
    dismiss, dismiss_polling, dismiss_parallel,
    js_dispatch_click, find_editor_frame, find_js_frame,
)
from automator.smart_editor import SmartEditorOne
from automator.job import PostingJob

__all__ = [
    # Value objects
    "AccountOption",
    "TitleOption",
    "Section",
    "Block",
    "HeadingBlock",
    "ParagraphBlock",
    "ImageBlock",
    "FeaturedImageBlock",
    "ListBlock",
    "QuoteBlock",
    "DividerBlock",
    "PublishOption",
    "RunSetting",
    # Editor
    "BlogEditor",
    "SmartEditorOne",
    # Orchestrator
    "PostingJob",
    # Functions
    "generate_title",
    "validate_template",
    "generate_paragraphs",
    "RateLimitError",
    # Extension API
    "BlockHandler",
    "ContentContext",
    "get_handler",
    "HANDLERS",
]
