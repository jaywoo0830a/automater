"""
tests/unit/factory/test_job_builder_spacing.py
-------------------------------------------------
Tests for SpacingRule.pattern integration into title generation.

Bug: _build_template() always uses " ".join(parts), ignoring
SpacingRule.pattern. ComboGenerator multiplies combinations by
spacing rules, but the pattern is never applied to the title.

Fix: _build_template(campaign, spacing_pattern) uses the pattern
to determine separators between tokens.

Pattern format: {slug: 0_or_1}
    1 (or missing) = space after this token
    0              = no space (glue to next token)
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from factory.job_builder import (
    _build_template,
    _build_title,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _token(slug, token_type="keyword", value=None, sort_order=0):
    return SimpleNamespace(
        slug=slug, token_type=token_type,
        palette=None, value=value, sort_order=sort_order,
    )


def _campaign(*tokens):
    return SimpleNamespace(
        tokens=list(tokens),
        affix_overrides=[],
    )


def _keyword(slug, value, cat_id=1):
    return SimpleNamespace(
        id=0, category=SimpleNamespace(slug=slug, id=cat_id),
        value=value, affixes=[],
    )


def _spacing_rule(pattern):
    return SimpleNamespace(pattern=pattern)


def _combo(keywords, tokens, spacing_rule=None):
    campaign = SimpleNamespace(
        layout=None, publish_preset=None, run_preset=None,
        affix_overrides=[], tokens=tokens,
    )
    return SimpleNamespace(
        keywords=keywords, campaign=campaign,
        spacing_rule=spacing_rule,
    )


# ===========================================================================
# _build_template with spacing_pattern
# ===========================================================================

class TestBuildTemplateSpacing:

    def test_no_pattern_defaults_to_spaces(self):
        """Backward compatibility: no pattern = all spaces."""
        campaign = _campaign(
            _token("region", sort_order=0),
            _token("subject", sort_order=1),
        )
        assert _build_template(campaign) == "{keyword:region} {keyword:subject}"

    def test_all_ones_same_as_default(self):
        """Pattern with all 1s = all spaces, same as no pattern."""
        campaign = _campaign(
            _token("region", sort_order=0),
            _token("subject", sort_order=1),
        )
        pattern = {"region": 1, "subject": 1}
        assert _build_template(campaign, pattern) == "{keyword:region} {keyword:subject}"

    def test_zero_glues_tokens(self):
        """Pattern 0 = no space between tokens."""
        campaign = _campaign(
            _token("region", sort_order=0),
            _token("subject", sort_order=1),
        )
        pattern = {"region": 0, "subject": 1}
        assert _build_template(campaign, pattern) == "{keyword:region}{keyword:subject}"

    def test_all_zeros_no_spaces(self):
        campaign = _campaign(
            _token("region", sort_order=0),
            _token("subject", sort_order=1),
            _token("salt_suffix", "pool", sort_order=2),
        )
        pattern = {"region": 0, "subject": 0, "salt_suffix": 0}
        assert _build_template(campaign, pattern) == "{keyword:region}{keyword:subject}{pool:salt_suffix}"

    def test_mixed_pattern(self):
        """Realistic: region과 subject 사이는 붙이고, subject 뒤에는 띄움."""
        campaign = _campaign(
            _token("region", sort_order=0),
            _token("subject", sort_order=1),
            _token("salt_suffix", "pool", sort_order=2),
        )
        pattern = {"region": 0, "subject": 1, "salt_suffix": 1}
        assert _build_template(campaign, pattern) == "{keyword:region}{keyword:subject} {pool:salt_suffix}"

    def test_literal_token_respects_spacing(self):
        campaign = _campaign(
            _token("region", sort_order=0),
            _token("_lit", "literal", value="과외", sort_order=1),
            _token("subject", sort_order=2),
        )
        pattern = {"region": 1, "_lit": 0, "subject": 1}
        assert _build_template(campaign, pattern) == "{keyword:region} 과외{keyword:subject}"

    def test_missing_slug_in_pattern_defaults_to_space(self):
        """Slugs not in the pattern default to space (1)."""
        campaign = _campaign(
            _token("region", sort_order=0),
            _token("subject", sort_order=1),
            _token("salt_suffix", "pool", sort_order=2),
        )
        pattern = {"region": 0}
        assert _build_template(campaign, pattern) == "{keyword:region}{keyword:subject} {pool:salt_suffix}"

    def test_last_token_spacing_value_is_ignored(self):
        """The last token's spacing value doesn't matter — nothing follows."""
        campaign = _campaign(
            _token("region", sort_order=0),
            _token("subject", sort_order=1),
        )
        pattern_with_last_zero = {"region": 1, "subject": 0}
        pattern_with_last_one = {"region": 1, "subject": 1}
        assert _build_template(campaign, pattern_with_last_zero) == "{keyword:region} {keyword:subject}"
        assert _build_template(campaign, pattern_with_last_one) == "{keyword:region} {keyword:subject}"

    def test_single_token_no_separator_needed(self):
        campaign = _campaign(_token("region", sort_order=0))
        pattern = {"region": 0}
        assert _build_template(campaign, pattern) == "{keyword:region}"

    def test_empty_tokens_returns_empty(self):
        campaign = _campaign()
        pattern = {"region": 0}
        assert _build_template(campaign, pattern) == ""

    def test_none_pattern_same_as_no_pattern(self):
        campaign = _campaign(
            _token("region", sort_order=0),
            _token("subject", sort_order=1),
        )
        assert _build_template(campaign, None) == "{keyword:region} {keyword:subject}"


# ===========================================================================
# _build_title with spacing_rule on combo
# ===========================================================================

class TestBuildTitleSpacing:

    def test_combo_without_spacing_rule_uses_spaces(self):
        """Backward compat: combo.spacing_rule is None = all spaces."""
        combo = _combo(
            keywords=[_keyword("region", "강남", 1), _keyword("subject", "수학", 2)],
            tokens=[
                _token("region", sort_order=0),
                _token("subject", sort_order=1),
            ],
            spacing_rule=None,
        )
        opt = _build_title(combo)
        assert opt.template == "{keyword:region} {keyword:subject}"

    def test_combo_with_spacing_rule_applies_pattern(self):
        combo = _combo(
            keywords=[_keyword("region", "강남", 1), _keyword("subject", "수학", 2)],
            tokens=[
                _token("region", sort_order=0),
                _token("subject", sort_order=1),
            ],
            spacing_rule=_spacing_rule({"region": 0, "subject": 1}),
        )
        opt = _build_title(combo)
        assert opt.template == "{keyword:region}{keyword:subject}"

    def test_combo_with_spacing_rule_three_tokens(self):
        combo = _combo(
            keywords=[_keyword("region", "강남", 1), _keyword("subject", "수학", 2)],
            tokens=[
                _token("region", sort_order=0),
                _token("_lit", "literal", value="과외", sort_order=1),
                _token("subject", sort_order=2),
            ],
            spacing_rule=_spacing_rule({"region": 1, "_lit": 0, "subject": 1}),
        )
        opt = _build_title(combo)
        assert opt.template == "{keyword:region} 과외{keyword:subject}"

    def test_combo_with_empty_pattern_uses_spaces(self):
        """Empty dict pattern = all defaults = all spaces."""
        combo = _combo(
            keywords=[_keyword("region", "강남", 1)],
            tokens=[
                _token("region", sort_order=0),
                _token("subject", sort_order=1),
            ],
            spacing_rule=_spacing_rule({}),
        )
        opt = _build_title(combo)
        assert opt.template == "{keyword:region} {keyword:subject}"

    def test_combo_missing_spacing_rule_attribute(self):
        """Combo without spacing_rule attr (old data) = all spaces."""
        campaign = SimpleNamespace(
            layout=None, publish_preset=None, run_preset=None,
            affix_overrides=[], tokens=[
                _token("region", sort_order=0),
                _token("subject", sort_order=1),
            ],
        )
        combo = SimpleNamespace(
            keywords=[_keyword("region", "강남", 1)],
            campaign=campaign,
        )
        opt = _build_title(combo)
        assert opt.template == "{keyword:region} {keyword:subject}"
