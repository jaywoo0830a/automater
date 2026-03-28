"""
tests/unit/automator/test_region.py
-----------------------------------
region.py 마스크 생성 단위 테스트.
"""

from PIL import Image
import pytest

from automator.region import parse_region


class TestAll:

    def test_all_mask_is_white(self):
        mask = parse_region("all", 100, 80)
        assert mask.mode == "L"
        assert mask.size == (100, 80)
        assert mask.getpixel((0, 0)) == 255
        assert mask.getpixel((50, 40)) == 255

    def test_empty_string_same_as_all(self):
        mask = parse_region("", 50, 50)
        assert mask.getpixel((0, 0)) == 255


class TestBorder:

    def test_border_px(self):
        mask = parse_region("border:10", 100, 100)
        # corner → inside border
        assert mask.getpixel((0, 0)) == 255
        assert mask.getpixel((5, 5)) == 255
        # center → outside border
        assert mask.getpixel((50, 50)) == 0

    def test_border_percent(self):
        mask = parse_region("border:10%", 200, 100)
        # min(200,100)=100, 10%=10px
        assert mask.getpixel((0, 0)) == 255
        assert mask.getpixel((50, 50)) == 0


class TestCenter:

    def test_center_60_percent(self):
        mask = parse_region("center:60%", 100, 100)
        # center
        assert mask.getpixel((50, 50)) == 255
        # corner
        assert mask.getpixel((0, 0)) == 0


class TestDirectional:

    def test_top_30_percent(self):
        mask = parse_region("top:30%", 100, 100)
        assert mask.getpixel((50, 10)) == 255
        assert mask.getpixel((50, 90)) == 0

    def test_bottom_30_percent(self):
        mask = parse_region("bottom:30%", 100, 100)
        assert mask.getpixel((50, 90)) == 255
        assert mask.getpixel((50, 10)) == 0

    def test_left_50_percent(self):
        mask = parse_region("left:50%", 100, 100)
        assert mask.getpixel((10, 50)) == 255
        assert mask.getpixel((90, 50)) == 0

    def test_right_50_percent(self):
        mask = parse_region("right:50%", 100, 100)
        assert mask.getpixel((90, 50)) == 255
        assert mask.getpixel((10, 50)) == 0


class TestRect:

    def test_rect(self):
        mask = parse_region("rect:10,10,30,30", 100, 100)
        assert mask.getpixel((20, 20)) == 255
        assert mask.getpixel((0, 0)) == 0

    def test_rect_bad_format(self):
        with pytest.raises(ValueError):
            parse_region("rect:10,10", 100, 100)


class TestRange:

    def test_border_range_px(self):
        """border:5 ~ 20 → 결과는 5~20px 사이."""
        for _ in range(10):
            mask = parse_region("border:5 ~ 20", 100, 100)
            # corner always inside border
            assert mask.getpixel((0, 0)) == 255
            # center always outside (5px 이상이면 50,50은 항상 밖)
            assert mask.getpixel((50, 50)) == 0

    def test_border_range_percent(self):
        mask = parse_region("border:5% ~ 15%", 200, 200)
        assert mask.getpixel((0, 0)) == 255
        assert mask.getpixel((100, 100)) == 0

    def test_top_range(self):
        """top:10% ~ 40% → 상단 영역 생성."""
        mask = parse_region("top:10% ~ 40%", 100, 100)
        assert mask.getpixel((50, 0)) == 255
        assert mask.getpixel((50, 99)) == 0


class TestUnknown:

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown region"):
            parse_region("circle:50", 100, 100)
