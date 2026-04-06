"""
automator
---------
Blog automation package.

Public interface
----------------
    JobRunner           — orchestrator: validate -> build -> execute
    PostingSpec         — frozen data contract (Zone A)
    BlogEditor          — abstract editor with 7 primitives
    SmartEditorOne      — Naver Smart Editor implementation

    AccountOption, TitleOption, PublishOption — config
    Section, Block types (7)    — post body structure
    BlockHandler, HANDLERS      — extension point for new block types

    TextGenerator, ImageProcessor, SelectorSource — ports (ABCs)
    GeminiGenerator, LocalImageProcessor          — concrete implementations
    StubTextGenerator, NoopImageProcessor          — test doubles

    generate_title()            — TitleOption -> str
    validate_template()         — raises ValueError on bad template

Usage
-----
    spec = PostingSpec(
        account=AccountOption(username="id", password="pw"),  # platform config goes to editor
        title="my title",  # or TitleOption(template=...)
        body=(Section(blocks=(ParagraphBlock(),)),),
    )
    runner = JobRunner(SpecValidator(), ContentBuilder(text_gen, img_proc))
    runner.run(spec, editor)
"""

from automator.options import (
    AccountOption, TitleOption, Section, Block,
    HeadingBlock, ParagraphBlock, ImageBlock, FeaturedImageBlock,
    ListBlock, QuoteBlock, DividerBlock,
    PublishOption,
)
from automator.contracts import PostingSpec
from automator.editor import BlogEditor
from automator.title_generator import generate_title, validate_template
from automator.paragraph_generator import (
    GeminiError, RateLimitError, SafetyBlockError,
    EmptyResponseError, PromptBlockedError,
    ServerError, AuthenticationError, InvalidRequestError,
)
from automator.block_handlers import BlockHandler, ContentContext, get_handler, HANDLERS
from automator.ports import TextGenerator, ImageProcessor, SelectorSource
from automator.stubs import StubTextGenerator, NoopImageProcessor, DictSelectorSource
from automator.gemini_generator import GeminiGenerator
from automator.local_processor import LocalImageProcessor
from automator.json_selector_source import JsonSelectorSource
from automator.yaml_selector_source import YamlSelectorSource
from automator.spec_validator import SpecValidator
from automator.content_builder import ContentBuilder
from automator.runner import JobRunner
from automator.smart_editor import SmartEditorOne

__all__ = [
    "PostingSpec", "AccountOption", "TitleOption", "Section", "Block",
    "HeadingBlock", "ParagraphBlock", "ImageBlock", "FeaturedImageBlock",
    "ListBlock", "QuoteBlock", "DividerBlock", "PublishOption",
    "BlogEditor", "SmartEditorOne",
    "JobRunner", "SpecValidator", "ContentBuilder",
    "TextGenerator", "ImageProcessor", "SelectorSource",
    "GeminiGenerator", "LocalImageProcessor", "JsonSelectorSource", "YamlSelectorSource",
    "StubTextGenerator", "NoopImageProcessor", "DictSelectorSource",
    "generate_title", "validate_template", "RateLimitError",
    "BlockHandler", "ContentContext", "get_handler", "HANDLERS",
]
