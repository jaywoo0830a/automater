"""api/step2_title.py — Step 2d: Full title preview (all pipeline data)."""
from __future__ import annotations
import random
from fastapi import APIRouter
from sqlalchemy import select
from api.deps import CurrentUser, DbSession
from api.schemas import (SpacingStylePreview, TitlePreviewInput, TitlePreviewResult)
from factory.models import CampaignPalette, Keyword, PaletteItem

router = APIRouter(prefix="/step2/title", tags=["step-2-title"])

@router.post("/preview", response_model=TitlePreviewResult)
def preview_title(body: TitlePreviewInput, user: CurrentUser, db: DbSession):
    tokens = sorted(body.title_tokens, key=lambda t: t.sort_order)
    warnings: list[str] = []
    rng = random.Random(42)

    # Build keyword values with affix overrides applied
    kw_map: dict[str, list[str]] = {}
    override_lookup = {(o.keyword_id, o.affix_id): o.active for o in body.affix_overrides}
    for sel in body.keyword_selections:
        rows = db.scalars(select(Keyword).where(Keyword.id.in_(sel.keyword_ids))).all()
        values = []
        for kw in rows:
            val = kw.value
            for affix in getattr(kw, "affixes", []):
                active = override_lookup.get((kw.id, affix.id), True)
                if not active:
                    if affix.type == "suffix" and val.endswith(affix.value):
                        val = val[:-len(affix.value)]
                    elif affix.type == "prefix" and val.startswith(affix.value):
                        val = val[len(affix.value):]
            values.append(val)
        kw_map[sel.slug] = values
        if not values:
            warnings.append(f"No keywords selected for '{sel.slug}'.")

    # Build pool values
    pool_map: dict[str, list[str]] = {}
    for t in tokens:
        if t.type == "pool":
            palette = db.scalars(select(CampaignPalette).join(CampaignPalette.token).where(
                CampaignPalette.token.has(slug=t.slug))).first()
            items = [i.value for i in palette.items if getattr(i, "active", True)] if palette else []
            pool_map[t.slug] = items
            if not items:
                warnings.append(f"Pool '{t.slug}' has no items.")

    # Spacing styles
    styles = body.spacing_styles
    if not styles:
        from api.schemas import SpacingStyle
        styles = [SpacingStyle(name="Default", pattern={t.slug: 1 for t in tokens})]

    # Compute combination count
    kw_slugs = [t.slug for t in tokens if t.type == "keyword"]
    kw_product = 1
    for s in kw_slugs:
        kw_product *= max(len(kw_map.get(s, [1])), 1)
    total = kw_product * len(styles)

    # Generate samples per style
    results: list[SpacingStylePreview] = []
    for style in styles:
        template = _build_template(tokens, style.pattern)
        samples = _generate(template, tokens, kw_map, pool_map, body.count, rng)
        results.append(SpacingStylePreview(name=style.name, template=template, samples=samples))

    return TitlePreviewResult(styles=results, total_combinations=total, warnings=warnings)

def _build_template(tokens, pattern):
    if not tokens: return ""
    parts = []
    for t in tokens:
        parts.append(t.value if t.type == "literal" else f"{{{t.slug}}}")
    result = parts[0]
    for i in range(1, len(parts)):
        sep = " " if pattern.get(tokens[i-1].slug, 1) else ""
        result += sep + parts[i]
    return result

def _generate(template, tokens, kw_map, pool_map, count, rng):
    samples = []
    for _ in range(count):
        vals = {}
        for t in tokens:
            if t.type == "keyword":
                pool = kw_map.get(t.slug, [])
                vals[t.slug] = rng.choice(pool) if pool else f"[{t.slug}]"
            elif t.type == "pool":
                pool = pool_map.get(t.slug, [])
                vals[t.slug] = rng.choice(pool) if pool else ""
        try:
            samples.append(template.format(**vals))
        except KeyError:
            samples.append(template)
    return samples
