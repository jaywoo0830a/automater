"""
factory
-------
Campaign management: keyword combinations, batch dispatch, and
Combination -> PostingJob translation.

Public modules:
    factory.db               — Engine creation, schema management
    factory.models           — ORM models (single source of truth)
                               User for auth + ownership
                               Affix, CampaignPalette, PaletteItem for
                               keyword derivation and runtime sampling
    factory.combo_generator  — Cartesian product of campaign keywords
    factory.keyword_picker   — Per-campaign keyword selection
    factory.dispatcher       — Assign combinations to accounts in batches
    factory.job_builder      — Translate Combination -> PostingJob
"""
