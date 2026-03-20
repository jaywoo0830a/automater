"""
tests/unit/api/test_utility.py
---------------------------------
Utility route unit tests — validateTitleTemplate, listBlockTypes.

Both endpoints are public (no auth required).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.app import create_app


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


class TestValidateTitleTemplate:

    def test_valid_template(self, client):
        resp = client.post("/validate/title-template", json={
            "template": "{region} {subject} {salt}",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert "region" in data["tokens"]
        assert "subject" in data["tokens"]
        assert "salt" in data["tokens"]

    def test_empty_template_invalid(self, client):
        resp = client.post("/validate/title-template", json={
            "template": "",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert data["error"] is not None

    def test_no_tokens_invalid(self, client):
        resp = client.post("/validate/title-template", json={
            "template": "just plain text",
        })
        data = resp.json()
        assert data["valid"] is False

    def test_empty_braces_invalid(self, client):
        resp = client.post("/validate/title-template", json={
            "template": "hello {}",
        })
        data = resp.json()
        assert data["valid"] is False

    def test_duplicate_tokens_invalid(self, client):
        resp = client.post("/validate/title-template", json={
            "template": "{region} {region}",
        })
        data = resp.json()
        assert data["valid"] is False


class TestListBlockTypes:

    def test_returns_list(self, client):
        resp = client.get("/block-types")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 7

    def test_each_block_has_type_and_label(self, client):
        data = client.get("/block-types").json()
        for block in data:
            assert "type" in block
            assert "label" in block

    def test_paragraph_block_exists(self, client):
        data = client.get("/block-types").json()
        types = [b["type"] for b in data]
        assert "paragraph" in types
        assert "image" in types
        assert "featured" in types
        assert "heading" in types
