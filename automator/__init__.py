"""
automator
---------
Blog automation package.

Quick start
-----------
    from automator import (
        PostingJob, AccountOption, TitleOption,
        TextBlock, ImageBlock, FeaturedBlock,
        MediaOption, PublishOption, SEOOption,
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
            ImageBlock(path="assets/images/1.jpg"),
            TextBlock(prompt="강남 수학 과외 홍보 블로그"),
            FeaturedBlock(path="assets/thumbnails/1.jpg"),
            TextBlock(prompt="후기 형식 마무리"),
        ])
        .with_media(MediaOption(
            pixel_jitter=True,
            featured_overlay_text="강남 수학",
            exif_description="강남 수학 과외",
        ))
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
    TextBlock,
    ImageBlock,
    FeaturedBlock,
    Block,
    MediaOption,
    PublishOption,
    SEOOption,
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
from automator.image_processor import ImageProcessor
from automator.asset_loader import AssetLoader

__all__ = [
    "AccountOption",
    "TitleOption",
    "TextBlock",
    "ImageBlock",
    "FeaturedBlock",
    "Block",
    "MediaOption",
    "PublishOption",
    "SEOOption",
    "RunSetting",
    "BlogEditor",
    "PostContent",
    "ParagraphStep",
    "ImageStep",
    "ThumbnailStep",
    "PostStep",
    "SmartEditorOne",
    "PostingJob",
    "ImageProcessor",
    "AssetLoader",
    "ParagraphGenerator",
]
