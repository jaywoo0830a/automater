"""api/step2_spacing.py — Step 2c: Spacing style preview."""
from __future__ import annotations
import random
from fastapi import APIRouter
from sqlalchemy import select
from api.deps import CurrentUser, DbSession
from api.schemas import (SpacingPreviewInput, SpacingPreviewResult, SpacingStylePreview)
from factory.models import Keyword

router = APIRouter(prefix="/step2/spacing", tags=["step-2-spacing"])

@router.post("/preview", response_model=SpacingPreviewResult)
def preview_spacing(body: SpacingPreviewInput, user: CurrentUser, db: DbSession):
    warnings: list[str] = []
    kw_map: dict[str, list[str]] = {}
    for sel in body.keyword_selections:
        rows = db.scalars(select(Keyword).where(Keyword.id.in_(sel.keyword_ids))).all()
        kw_map[sel.slug] = [r.value for r in rows]

    rng = random.Random(42)
    style_results: list[SpacingStylePreview] = []

    for style in body.styles:
        template = _apply_pattern(body.token_slugs, style.pattern)
        samples = _generate_samples(template, body.token_slugs, kw_map, body.count, rng)
        style_results.append(SpacingStylePreview(name=style.name, template=template, samples=samples))

    return SpacingPreviewResult(
        styles=style_results,
        combination_multiplier=len(body.styles),
        warnings=warnings,
    )

def _apply_pattern(slugs: list[str], pattern: dict[str, int]) -> str:
    if not slugs: return ""
    parts = [f"{{{s}}}" for s in slugs]
    result = parts[0]
    for i in range(1, len(parts)):
        sep = " " if pattern.get(slugs[i-1], 1) else ""
        result += sep + parts[i]
    return result

def _generate_samples(template: str, slugs: list[str], kw_map: dict[str, list[str]],
                      count: int, rng: random.Random) -> list[str]:
    samples = []
    for _ in range(count):
        values = {}
        for slug in slugs:
            pool = kw_map.get(slug, [])
            values[slug] = rng.choice(pool) if pool else f"[{slug}]"
        try:
            samples.append(template.format(**values))
        except KeyError:
            samples.append(template)
    return samples
