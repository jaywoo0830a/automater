"""
automator
---------
Naver Blog automation package.

Quick start
-----------
    from automator import (
        NaverBlogJob,
        AccountOption, TitleOption, ContentOption, MetaOption, RunSetting,
        BlogEditor, PostContent, PostStep,
        SmartEditorOne,
    )

    job = (
        NaverBlogJob
        .for_account(AccountOption(
            naver_id="my_id",
            naver_pw="my_pw",
            blog_id="my_blog",
        ))
        .with_title(TitleOption(
            template="지역+과목+학습형태+솔트",
            learning_type="과외",
            include_suffix=True,
        ))
        .with_content(ContentOption(
            preview_images=["images/preview_1.jpg", "images/preview_2.jpg"],
            thumbnail_images=["images/thumbnail.jpg"],
            layout=[
                "Image 1",
                "Image 2",
                "Paragraph 1",
                "Thumbnail 1",
                "Paragraph 2",
                "Paragraph 3",
            ],
        ))
        .with_meta(MetaOption(min_tags=10, max_tags=15))
        .with_setting(RunSetting(post_interval=30))
    )

    # editor requires a live Playwright Page:
    # Dry run (default — no publish):
    # success = job.run(SmartEditorOne(page, job._account.write_url))
    # Live publish (explicit):
    # success = job.run(SmartEditorOne(page, job._account.write_url, dry_run=False))
"""

from automator.paragraph_generator import ParagraphGenerator
from automator.options import (
    AccountOption,
    TitleOption,
    ContentOption,
    MetaOption,
    RunSetting,
)
from automator.editor import BlogEditor, PostContent, PostStep
from automator.browser_actions import (
    click_if_visible, click_polling,
    dismiss, dismiss_polling, dismiss_parallel,
    js_dispatch_click, find_editor_frame, find_js_frame,
)
from automator.smart_editor import SmartEditorOne
from automator.job import NaverBlogJob

__all__ = [
    "AccountOption",
    "TitleOption",
    "ContentOption",
    "MetaOption",
    "RunSetting",
    "BlogEditor",
    "PostContent",
    "PostStep",
    "SmartEditorOne",
    "NaverBlogJob",
]
