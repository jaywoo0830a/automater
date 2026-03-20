"""
api/routes/utility.py — validateTitleTemplate, listBlockTypes
"""

from __future__ import annotations

from dataclasses import fields as dc_fields

from fastapi import APIRouter

from api.schemas import TemplateValidation, BlockTypeInfo
from automator.title_generator import validate_template, _TOKEN_RE
from automator.block_factory import FACTORIES
from automator.options import (
    ParagraphBlock, ImageBlock, FeaturedImageBlock,
    HeadingBlock, ListBlock, QuoteBlock, DividerBlock,
)

router = APIRouter(tags=["utility"])

_LABELS = {
    "paragraph": "Paragraph",
    "image": "Body image",
    "featured": "Featured image",
    "heading": "Heading",
    "list": "List",
    "quote": "Quote",
    "divider": "Divider",
}


def _config_schema(cls: type) -> dict:
    """Extract a simplified JSON schema from a frozen dataclass."""
    schema: dict = {}
    for f in dc_fields(cls):
        name = f.name
        t = f.type
        if "str" in str(t):
            schema[name] = {"type": "string"}
        elif "int" in str(t):
            schema[name] = {"type": "integer"}
        elif "float" in str(t):
            schema[name] = {"type": "number"}
        elif "bool" in str(t):
            schema[name] = {"type": "boolean"}
        else:
            schema[name] = {"type": "string"}
        if f.default is not f.default_factory if hasattr(f, "default_factory") else True:
            if f.default is not f.default:
                pass
    return schema


@router.post("/validate/title-template", response_model=TemplateValidation)
def validate_title_template(body: dict):
    template = body.get("template", "")
    try:
        validate_template(template)
        tokens = _TOKEN_RE.findall(template)
        return TemplateValidation(valid=True, tokens=tokens, error=None)
    except ValueError as e:
        return TemplateValidation(valid=False, tokens=[], error=str(e))


@router.get("/block-types", response_model=list[BlockTypeInfo])
def list_block_types():
    result = []
    for type_key, cls in FACTORIES.items():
        schema = {}
        for f in dc_fields(cls):
            schema[f.name] = {"type": type(f.default).__name__ if f.default is not f.default else "string"}
        result.append(BlockTypeInfo(
            type=type_key,
            label=_LABELS.get(type_key, type_key),
            config_schema=schema,
        ))
    return result
