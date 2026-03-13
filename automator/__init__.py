"""
automator
---------
Naver Blog automation package.

Quick start
-----------
    from automator import (
        NaverBlogJob,
        AccountOption, TitleOption, ContentOption, MetaOption, RunSetting,
        BlogEditor, PostContent,
        SmartEditorOne,
    )

    job = (
        NaverBlogJob
        .for_account(AccountOption(
            naver_id="my_id",
            naver_pw="my_pw",
            blog_id="my_blog",
        ))
        .with_title(TitleOption(subjects=["국어", "수학"]))
        .with_content(ContentOption(paragraph_count=5))
        .with_meta(MetaOption(min_tags=10, max_tags=15))
        .with_setting(RunSetting(post_interval=30))
    )

    # editor requires a live Playwright Page:
    # success = job.run(SmartEditorOne(page, job._account.write_url))
"""

from automator.options import (
    AccountOption,
    TitleOption,
    ContentOption,
    MetaOption,
    RunSetting,
)
from automator.editor import BlogEditor, PostContent
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
    "SmartEditorOne",
    "NaverBlogJob",
]
