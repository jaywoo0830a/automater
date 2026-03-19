"""
automator
---------
Blog automation package.

Quick start
-----------
    from automator import (
        PostingJob,
        AccountOption, TitleOption, PublishOption, RunSetting,
        Section, BlockMeta,
        HeadingBlock, ParagraphBlock, ImageBlock, FeaturedImageBlock,
        ListBlock, QuoteBlock, DividerBlock,
        SmartEditorOne,
    )

    job = (
        PostingJob
        .for_account(AccountOption(
            username="my_id",
            password="my_pw",
            meta={"blog_id": "my_blog"},
        ))
        .with_title(TitleOption(fixed_title="강남 수학 과외 추천"))
        .with_body([
            Section(
                role="intro",
                blocks=(
                    HeadingBlock(level=2, text="강남 수학 과외 안내"),
                    ParagraphBlock(
                        keyword="강남 수학 과외",
                        tone="review",
                        min_chars=250,
                    ),
                ),
            ),
            Section(
                role="closing",
                blocks=(
                    ImageBlock(path="assets/images/1.jpg"),
                    FeaturedImageBlock(
                        path="assets/thumbnails/1.jpg",
                        overlay_text="강남 수학 과외",
                    ),
                ),
            ),
        ])
        .with_publish(PublishOption(mode="immediate"))
    )

    write_url = f"https://blog.naver.com/{job._account.meta['blog_id']}?Redirect=Write&"
    with SmartEditorOne(page, write_url) as editor:
        job.run(editor)
"""

from automator.paragraph_generator import ParagraphGenerator
from automator.options import (
    AccountOption,
    TitleOption,
    Section,
    BlockMeta,
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
from automator.editor import (
    BlogEditor, PostContent,
    ParagraphStep, ImageStep, ThumbnailStep, PostStep,
)
from automator.browser_actions import (
    click_if_visible, click_polling,
    dismiss, dismiss_polling, dismiss_parallel,
    js_dispatch_click, find_editor_frame, find_js_frame,
)
from automator.smart_editor import SmartEditorOne
from automator.job import PostingJob
from automator.asset_loader import AssetLoader

__all__ = [
    "AccountOption",
    "TitleOption",
    "Section",
    "BlockMeta",
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
    "BlogEditor",
    "PostContent",
    "ParagraphStep",
    "ImageStep",
    "ThumbnailStep",
    "PostStep",
    "SmartEditorOne",
    "PostingJob",
    "AssetLoader",
    "ParagraphGenerator",
]
