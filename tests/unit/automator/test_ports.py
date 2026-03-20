"""
tests/unit/test_ports.py
--------------------------
Verify test doubles conform to port ABCs.
"""

import pytest

from automator.ports import TextGenerator, ImageProcessor, SelectorSource
from automator.stubs import StubTextGenerator, NoopImageProcessor, DictSelectorSource


def test_stub_text_gen_is_text_generator():
    assert isinstance(StubTextGenerator(), TextGenerator)


def test_stub_text_gen_returns_count():
    gen = StubTextGenerator(["a", "b"])
    assert len(gen.generate("prompt", 3)) == 3


def test_noop_img_proc_is_image_processor():
    assert isinstance(NoopImageProcessor(), ImageProcessor)


def test_noop_returns_input_unchanged():
    proc = NoopImageProcessor()
    data = b"jpeg bytes"
    assert proc.process_body(data, None) is data
    assert proc.process_featured(data, None) is data


def test_noop_build_filename():
    proc = NoopImageProcessor()
    assert proc.build_filename("preview", 1, "test") == "preview_001_test.jpg"


def test_dict_selector_source_is_selector_source():
    assert isinstance(DictSelectorSource({}), SelectorSource)


def test_dict_selector_source_returns_value():
    loader = object()
    src = DictSelectorSource({"editor": loader})
    assert src.load("editor") is loader


def test_dict_selector_source_missing_raises():
    src = DictSelectorSource({})
    with pytest.raises(FileNotFoundError, match="no entry"):
        src.load("missing")
