"""
factory/bulk_importer.py
--------------------------
BulkImporter — automates the full keyword-to-combination pipeline.

Designed for non-technical users like Eric:
    "Here's an Excel of regions, generate combinations."

Usage:
    importer = BulkImporter(session, campaign_id)
    importer.import_keywords({
        "region": ["수리동", "산본동"],
        "subject": ["수학", "영어"],
    })
    importer.import_pools({
        "salt_prefix": ["검증된", "전문"],
        "salt_suffix": ["강력 추천", "즉시 가능"],
    })
    result = importer.generate()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from factory.affix_detector import detect_affixes as _detect_affixes
from factory.combo_generator import ComboGenerator
from factory.excel_parser import parse_rows, resolve_headers
from factory.models import (
    Affix,
    BatchItem,
    CampaignAffixOverride,
    CampaignKeywordPick,
    CampaignPalette,
    CampaignSlot,
    Combination,
    Keyword,
    KeywordCategory,
    PaletteItem,
    SpacingRule,
    TemplateToken,
    combination_keywords,
)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ImportResult:
    """Outcome of import_keywords()."""
    categories_created: int = 0
    keywords_created:   int = 0
    keywords_existing:  int = 0
    tokens_created:     int = 0
    picks_set:          int = 0


@dataclass(frozen=True)
class GenerateResult:
    """Outcome of generate()."""
    combinations_generated: int = 0
    combinations_stale:     int = 0
    spacing_rules_created:  int = 0


@dataclass(frozen=True)
class PoolImportResult:
    """Outcome of import_pools()."""
    pools_created:  int = 0
    items_created:  int = 0
    items_existing: int = 0


@dataclass(frozen=True)
class ResetResult:
    """Outcome of soft_reset() / hard_reset()."""
    combinations_removed:   int = 0
    combinations_preserved: int = 0
    tokens_removed:         int = 0
    picks_removed:          int = 0
    spacing_rules_removed:  int = 0


# ---------------------------------------------------------------------------
# Validation — pure function, no DB
# ---------------------------------------------------------------------------

def validate_import_data(data: dict[str, list[str]]) -> None:
    """
    Validate the import data structure.

    Raises ValueError if data is malformed.
    """
    if not data:
        raise ValueError("import data must not be empty")

    for slug, values in data.items():
        if not isinstance(slug, str) or not slug.strip():
            raise ValueError(
                f"category slug must be a non-empty string, got {slug!r}"
            )
        if not values:
            raise ValueError(
                f"keyword list for '{slug}' must not be empty"
            )
        for v in values:
            if not isinstance(v, str) or not v.strip():
                raise ValueError(
                    f"keyword value must be a non-empty string, "
                    f"got {v!r} in '{slug}'"
                )


# ---------------------------------------------------------------------------
# BulkImporter
# ---------------------------------------------------------------------------

class BulkImporter:
    """
    Automate keyword registration and combination generation.

    Two-step workflow:
        1. import_keywords(data) — upsert categories, keywords, tokens, picks
        2. generate()            — ensure spacing rule, run ComboGenerator

    Args:
        session:     Active SQLAlchemy session (caller manages transaction).
        campaign_id: Target campaign ID.
    """

    def __init__(self, session: Session, campaign_id: int) -> None:
        self._session = session
        self._campaign_id = campaign_id

    # ------------------------------------------------------------------
    # Step 0: import_from_excel — Korean headers → import_keywords
    # ------------------------------------------------------------------

    def import_from_excel(
        self,
        headers: list[str],
        rows: list[list],
        header_map: dict[str, str] | None = None,
    ) -> ImportResult:
        """
        Parse tabular data and import keywords with header resolution.

        Resolves Korean headers to slugs via:
            1. Explicit header_map (highest priority)
            2. KeywordCategory.name lookup from DB
            3. ASCII slug passthrough (e.g. "region" stays "region")

        Args:
            headers:    Column headers (Korean or English).
            rows:       List of rows, each a list of cell values.
            header_map: Optional explicit {display_name: slug} mapping.

        Returns:
            ImportResult — same as import_keywords.

        Raises:
            ValueError: If any header cannot be resolved to a slug.
        """
        raw_data = parse_rows(headers, rows)
        if not raw_data:
            raise ValueError("parsed data is empty — no values found")

        category_names = self._load_category_name_map()
        resolved = resolve_headers(raw_data, header_map, category_names)
        return self.import_keywords(resolved)

    # ------------------------------------------------------------------
    # Step 1: import_keywords
    # ------------------------------------------------------------------

    def import_keywords(
        self,
        data: dict[str, list[str]],
        auto_detect_affixes: bool = False,
    ) -> ImportResult:
        """
        Upsert categories, keywords, tokens, slots, and picks.

        Args:
            data:                 {category_slug: [keyword_values]}
            auto_detect_affixes:  If True, detect Korean suffixes/prefixes
                                  and auto-link them to keywords.

        Returns:
            ImportResult with counts of created/existing entities.
        """
        validate_import_data(data)

        categories_created = 0
        keywords_created = 0
        keywords_existing = 0
        tokens_created = 0
        picks_set = 0

        existing_tokens = self._load_existing_tokens()
        all_tokens = self._load_all_tokens()
        next_sort_order = max(
            (t.sort_order for t in all_tokens.values()), default=-1
        ) + 1

        for slug, raw_values in data.items():
            values = list(dict.fromkeys(v.strip() for v in raw_values))

            category, created = self._upsert_category(slug)
            if created:
                categories_created += 1

            keywords: list[Keyword] = []
            for value in values:
                keyword, created = self._upsert_keyword(category.id, value)
                if created:
                    keywords_created += 1
                else:
                    keywords_existing += 1
                keywords.append(keyword)

            if slug not in existing_tokens:
                token = self._create_token_and_slot(
                    slug, category.id, next_sort_order,
                )
                tokens_created += 1
                next_sort_order += 1

            keyword_ids = [kw.id for kw in keywords]
            picks_set += self._set_picks(category.id, keyword_ids)

            if auto_detect_affixes:
                self._auto_link_affixes(values, keywords)

        return ImportResult(
            categories_created=categories_created,
            keywords_created=keywords_created,
            keywords_existing=keywords_existing,
            tokens_created=tokens_created,
            picks_set=picks_set,
        )

    # ------------------------------------------------------------------
    # Step 1b: import_pools (optional)
    # ------------------------------------------------------------------

    def import_pools(self, data: dict[str, list[str]]) -> PoolImportResult:
        """
        Create pool-type tokens with palette items.

        Args:
            data: {pool_slug: [item_values]}
                  e.g. {"salt_prefix": ["검증된", "전문"]}

        Returns:
            PoolImportResult with counts.
        """
        validate_import_data(data)

        pools_created = 0
        items_created = 0
        items_existing = 0

        all_tokens = self._load_all_tokens()
        next_sort_order = max(
            (t.sort_order for t in all_tokens.values()), default=-1
        ) + 1

        for slug, values in data.items():
            token = all_tokens.get(slug)

            if token is None:
                token = TemplateToken(
                    campaign_id=self._campaign_id,
                    slug=slug,
                    token_type="pool",
                    sort_order=next_sort_order,
                )
                self._session.add(token)
                self._session.flush()

                palette = CampaignPalette(
                    token_id=token.id, strategy="random",
                )
                self._session.add(palette)
                self._session.flush()

                pools_created += 1
                next_sort_order += 1
                all_tokens[slug] = token
            else:
                palette = token.palette

            existing_values = {
                item.value for item in palette.items
            }

            for value in values:
                v = value.strip()
                if v in existing_values:
                    items_existing += 1
                    continue
                self._session.add(PaletteItem(
                    palette_id=palette.token_id,
                    value=v,
                    sort_order=len(existing_values) + items_created,
                ))
                items_created += 1

            self._session.flush()

        return PoolImportResult(
            pools_created=pools_created,
            items_created=items_created,
            items_existing=items_existing,
        )

    # ------------------------------------------------------------------
    # Step 2: generate
    # ------------------------------------------------------------------

    def generate(
        self,
        spacing_patterns: list[dict[str, Any]] | None = None,
    ) -> GenerateResult:
        """
        Clean up stale combinations, ensure spacing rules, generate new ones.

        Stale = combinations referencing keywords not in current picks,
        but only if they have no batch_items (never dispatched).

        Args:
            spacing_patterns: List of pattern dicts for SpacingRule.
                              If None, a default pattern is created.

        Returns:
            GenerateResult with counts.
        """
        stale_removed = self._remove_stale_combinations()
        rules_created = self._ensure_spacing_rules(spacing_patterns)

        generator = ComboGenerator(self._session, self._campaign_id)
        count = generator.run()

        return GenerateResult(
            combinations_generated=count,
            combinations_stale=stale_removed,
            spacing_rules_created=rules_created,
        )

    # ------------------------------------------------------------------
    # Step 3: reset
    # ------------------------------------------------------------------

    def soft_reset(self) -> ResetResult:
        """
        Delete undispatched combinations only.

        Preserves:
            - Combinations with any batch_items (including pending)
            - Tokens, slots, palettes, picks, spacing rules

        Returns:
            ResetResult with removal counts.
        """
        combos = self._session.scalars(
            select(Combination).where(
                Combination.campaign_id == self._campaign_id,
            )
        ).all()

        removed = 0
        preserved = 0
        for combo in combos:
            if combo.batch_items:
                preserved += 1
                continue
            self._session.delete(combo)
            removed += 1

        if removed:
            self._session.flush()

        return ResetResult(
            combinations_removed=removed,
            combinations_preserved=preserved,
        )

    def hard_reset(self) -> ResetResult:
        """
        Delete everything except dispatched combinations and their batches.

        Removes: undispatched combos, picks, tokens (cascade: slots,
        palettes, items), spacing rules, affix overrides.

        Preserves:
            - Combinations with any batch_items (including pending)
            - Batches and batch_items (dispatch history)

        Returns:
            ResetResult with removal counts.
        """
        soft = self.soft_reset()

        picks = self._session.scalars(
            select(CampaignKeywordPick).where(
                CampaignKeywordPick.campaign_id == self._campaign_id,
            )
        ).all()
        picks_removed = len(picks)
        for pick in picks:
            self._session.delete(pick)

        tokens = self._session.scalars(
            select(TemplateToken).where(
                TemplateToken.campaign_id == self._campaign_id,
            )
        ).all()
        tokens_removed = len(tokens)
        for token in tokens:
            self._session.delete(token)

        rules = self._session.scalars(
            select(SpacingRule).where(
                SpacingRule.campaign_id == self._campaign_id,
            )
        ).all()
        rules_removed = len(rules)
        for rule in rules:
            self._session.delete(rule)

        overrides = self._session.scalars(
            select(CampaignAffixOverride).where(
                CampaignAffixOverride.campaign_id == self._campaign_id,
            )
        ).all()
        for override in overrides:
            self._session.delete(override)

        self._session.flush()

        return ResetResult(
            combinations_removed=soft.combinations_removed,
            combinations_preserved=soft.combinations_preserved,
            tokens_removed=tokens_removed,
            picks_removed=picks_removed,
            spacing_rules_removed=rules_removed,
        )

    # ------------------------------------------------------------------
    # Private — upsert helpers
    # ------------------------------------------------------------------

    def _load_existing_tokens(self) -> dict[str, TemplateToken]:
        tokens = self._session.scalars(
            select(TemplateToken).where(
                TemplateToken.campaign_id == self._campaign_id,
                TemplateToken.token_type == "keyword",
            )
        ).all()
        return {t.slug: t for t in tokens}

    def _load_all_tokens(self) -> dict[str, TemplateToken]:
        tokens = self._session.scalars(
            select(TemplateToken).where(
                TemplateToken.campaign_id == self._campaign_id,
            )
        ).all()
        return {t.slug: t for t in tokens}

    def _load_category_name_map(self) -> dict[str, str]:
        """Load {name: slug} lookup from all KeywordCategory rows."""
        categories = self._session.scalars(select(KeywordCategory)).all()
        return {c.name: c.slug for c in categories}

    def _upsert_category(
        self, slug: str,
    ) -> tuple[KeywordCategory, bool]:
        """Return (category, was_created)."""
        existing = self._session.scalars(
            select(KeywordCategory).where(KeywordCategory.slug == slug)
        ).first()
        if existing:
            return existing, False

        category = KeywordCategory(name=slug, slug=slug)
        self._session.add(category)
        self._session.flush()
        return category, True

    def _upsert_keyword(
        self, category_id: int, value: str,
    ) -> tuple[Keyword, bool]:
        """Return (keyword, was_created)."""
        existing = self._session.scalars(
            select(Keyword).where(
                Keyword.category_id == category_id,
                Keyword.value == value,
            )
        ).first()
        if existing:
            return existing, False

        keyword = Keyword(
            category_id=category_id,
            value=value,
            display_value=value,
            active=True,
        )
        self._session.add(keyword)
        self._session.flush()
        return keyword, True

    def _create_token_and_slot(
        self, slug: str, category_id: int, sort_order: int,
    ) -> TemplateToken:
        token = TemplateToken(
            campaign_id=self._campaign_id,
            slug=slug,
            token_type="keyword",
            sort_order=sort_order,
        )
        self._session.add(token)
        self._session.flush()

        slot = CampaignSlot(token_id=token.id, category_id=category_id)
        self._session.add(slot)
        self._session.flush()
        return token

    def _set_picks(
        self, category_id: int, keyword_ids: list[int],
    ) -> int:
        """Replace picks for this campaign + category with the given IDs."""
        existing = self._session.scalars(
            select(CampaignKeywordPick).where(
                CampaignKeywordPick.campaign_id == self._campaign_id,
                CampaignKeywordPick.category_id == category_id,
            )
        ).all()
        for pick in existing:
            self._session.delete(pick)
        self._session.flush()

        for kw_id in keyword_ids:
            self._session.add(CampaignKeywordPick(
                campaign_id=self._campaign_id,
                category_id=category_id,
                keyword_id=kw_id,
            ))
        self._session.flush()
        return len(keyword_ids)

    def _ensure_spacing_rules(
        self, patterns: list[dict[str, Any]] | None,
    ) -> int:
        """Create spacing rules if none exist. Returns count created."""
        existing = self._session.scalars(
            select(SpacingRule).where(
                SpacingRule.campaign_id == self._campaign_id,
                SpacingRule.active == True,  # noqa: E712
            )
        ).all()

        if existing:
            return 0

        if not patterns:
            tokens = self._session.scalars(
                select(TemplateToken).where(
                    TemplateToken.campaign_id == self._campaign_id,
                    TemplateToken.token_type == "keyword",
                )
            ).all()
            patterns = [{t.slug: 1 for t in tokens}]

        created = 0
        for pattern in patterns:
            self._session.add(SpacingRule(
                campaign_id=self._campaign_id,
                pattern=pattern,
                description="bulk import",
                active=True,
            ))
            created += 1
        self._session.flush()
        return created

    def _remove_stale_combinations(self) -> int:
        """
        Remove combinations whose keywords are not in current picks.

        Only removes combinations with no batch_items (never dispatched).
        Combinations already assigned to batches are preserved.

        Returns the number of removed combinations.
        """
        picked_ids = self._current_picked_keyword_ids()
        if not picked_ids:
            return 0

        combos = self._session.scalars(
            select(Combination).where(
                Combination.campaign_id == self._campaign_id,
            )
        ).all()

        removed = 0
        for combo in combos:
            combo_kw_ids = {kw.id for kw in combo.keywords}
            if combo_kw_ids.issubset(picked_ids):
                continue

            if combo.batch_items:
                continue

            self._session.delete(combo)
            removed += 1

        if removed:
            self._session.flush()
        return removed

    def _current_picked_keyword_ids(self) -> set[int]:
        """Load all keyword IDs currently picked for this campaign."""
        picks = self._session.scalars(
            select(CampaignKeywordPick).where(
                CampaignKeywordPick.campaign_id == self._campaign_id,
            )
        ).all()
        return {p.keyword_id for p in picks}

    def _auto_link_affixes(
        self,
        values: list[str],
        keywords: list[Keyword],
    ) -> None:
        """
        Detect affixes in values and link them to keywords.

        For each detected affix:
            1. Upsert the Affix row (global dictionary)
            2. Link matching keywords via keyword_affixes M2M
        """
        detected = _detect_affixes(values)
        if not detected:
            return

        for affix_type, affix_value in detected:
            affix = self._upsert_affix(affix_type, affix_value)

            for keyword in keywords:
                matches = (
                    (affix_type == "suffix" and keyword.value.endswith(affix_value))
                    or (affix_type == "prefix" and keyword.value.startswith(affix_value))
                )
                if matches and affix not in keyword.affixes:
                    keyword.affixes.append(affix)

        self._session.flush()

    def _upsert_affix(self, affix_type: str, value: str) -> Affix:
        """Return existing or newly created Affix row."""
        existing = self._session.scalars(
            select(Affix).where(
                Affix.type == affix_type,
                Affix.value == value,
            )
        ).first()
        if existing:
            return existing

        affix = Affix(type=affix_type, value=value)
        self._session.add(affix)
        self._session.flush()
        return affix
