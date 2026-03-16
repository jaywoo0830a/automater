"""
automator
---------
Naver Blog automation package.

Quick start
-----------
    from automator import NaverBlogJob, AccountOption, TitleOption, ContentOption, MetaOption
    from automator import SmartEditorOne, SEOOption

    job = (
        NaverBlogJob
        .for_account(AccountOption(
            naver_id="my_id",
            naver_pw="my_pw",
            blog_id="my_blog",
        ))
        .with_title(TitleOption(fixed_title="강남 수학 과외"))
        .with_content(AssetLoader().to_content_option(paragraphs=3))
        .with_seo(SEOOption(
            keyword="강남 수학 과외",
            tone="review_style",
        ))
        .with_image(ImageOption(
            pixel_jitter     = True,
            thumbnail_text   = "강남 수학 과외",
            exif_description = "강남 수학 과외",
            upload_delay_ms  = 1500,
        ))
        .with_meta(MetaOption())
    )

    # editor requires a live Playwright Page:
    with SmartEditorOne(page, job._account.write_url) as editor:
        job.run(editor)
"""

from automator.paragraph_generator import ParagraphGenerator
from automator.options import (
    AccountOption,
    TitleOption,
    ContentOption,
    MetaOption,
    RunSetting,
    SEOOption,
    ImageOption,
)
from automator.editor import BlogEditor, PostContent, PostStep
from automator.browser_actions import (
    click_if_visible, click_polling,
    dismiss, dismiss_polling, dismiss_parallel,
    js_dispatch_click, find_editor_frame, find_js_frame,
)
from automator.smart_editor import SmartEditorOne
from automator.job import NaverBlogJob
from automator.image_processor import ImageProcessor
from automator.asset_loader import AssetLoader

__all__ = [
    "AccountOption",
    "TitleOption",
    "ContentOption",
    "MetaOption",
    "RunSetting",
    "SEOOption",
    "ImageOption",
    "BlogEditor",
    "PostContent",
    "PostStep",
    "SmartEditorOne",
    "NaverBlogJob",
    "ImageProcessor",
    "AssetLoader",
]
