"""
factory
-------
Campaign management: keyword combinations, batch dispatch, and
Combination -> PostingSpec translation.

Public modules:
    factory.db               — Engine creation, schema management
    factory.models           — ORM models (single source of truth)
                               User for auth + ownership
                               PostLayout, LayoutSlot for dynamic body
                               PublishPreset, RunPreset (JSON config)
                               Affix, CampaignAffixOverride,
                               TemplateToken, CampaignPalette,
                               PaletteItem for keyword derivation,
                               template token resolution, and
                               runtime sampling
    factory.combo_generator  — Cartesian product of campaign keywords
    factory.bulk_importer   — Excel-to-combinations import pipeline
    factory.excel_parser    — Excel file / tabular data parsing
    factory.affix_detector  — Korean suffix/prefix auto-detection
    factory.keyword_picker   — Per-campaign keyword selection
    factory.dispatcher       — Assign combinations to accounts in batches
    factory.job_builder      — Translate Combination -> PostingSpec
                               (uses layout + presets when available)
"""
