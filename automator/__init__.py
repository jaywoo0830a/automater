"""
automator
---------
Naver Blog automation package.

Public API:
    PostContent      — value object describing what to post
    BlogEditor       — abstract editor interface
    SmartEditorOne   — Naver Smart Editor One implementation
    NaverBlogJob     — orchestrates a publish run
"""

from automator.editor import BlogEditor, PostContent
from automator.smart_editor import SmartEditorOne
from automator.job import NaverBlogJob

__all__ = [
    "BlogEditor",
    "PostContent",
    "SmartEditorOne",
    "NaverBlogJob",
]
