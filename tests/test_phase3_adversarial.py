"""Phase 3 adversarial / format / API tests."""

from __future__ import annotations

import os
import tempfile

import pytest

_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_DB.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_DB.name}"


@pytest.fixture(scope="module")
def db_ready():
    from database.session import reset_engine, init_db
    import config.settings as settings_mod
    import agent_os.models_db  # noqa: F401
    import knowledge_fabric.models_db  # noqa: F401

    os.environ["DATABASE_URL"] = f"sqlite:///{_DB.name}"
    if hasattr(settings_mod.get_settings, "cache_clear"):
        settings_mod.get_settings.cache_clear()
    reset_engine()
    init_db(f"sqlite:///{_DB.name}")
    yield
    reset_engine()
    try:
        os.unlink(_DB.name)
    except OSError:
        pass


def test_unsupported_pdf_rejected(db_ready):
    from knowledge_fabric.service import KnowledgeFabric
    from core.errors import ValidationError

    kf = KnowledgeFabric()
    with pytest.raises(ValidationError, match="Unsupported"):
        kf.ingest_document(
            organisation_id="org-f",
            content="%PDF-1.4 fake",
            content_type="application/pdf",
            title="x",
        )


def test_html_normalize_and_search(db_ready):
    from knowledge_fabric.service import KnowledgeFabric

    kf = KnowledgeFabric()
    d = kf.ingest_document(
        organisation_id="org-h",
        content="<html><body><h1>Growth</h1><p>Revenue increased twenty percent.</p></body></html>",
        content_type="text/html",
        title="html",
    )
    assert d["chunk_count"] >= 1
    hits = kf.search(organisation_id="org-h", query="Revenue increased", strategy="lexical", top_k=3)
    assert hits["hits"]


def test_kf_api_ingest_search_isolation(db_ready):
    from fastapi.testclient import TestClient
    from api.main import app

    with TestClient(app) as client:
        r = client.post(
            "/bi/kf/ingest",
            json={"content": "OrgAPI exclusive zeta-api-token", "title": "t", "content_type": "text/plain"},
            headers={"X-Organisation-Id": "org-api-a", "X-User-Id": "u"},
        )
        assert r.status_code == 200, r.text
        s = client.post(
            "/bi/kf/search",
            json={"query": "zeta-api-token", "strategy": "lexical"},
            headers={"X-Organisation-Id": "org-api-b", "X-User-Id": "u"},
        )
        assert s.status_code == 200
        assert all("zeta-api-token" not in h.get("content", "") for h in s.json().get("hits", []))
        s2 = client.post(
            "/bi/kf/search",
            json={"query": "zeta-api-token", "strategy": "lexical"},
            headers={"X-Organisation-Id": "org-api-a", "X-User-Id": "u"},
        )
        assert any("zeta-api-token" in h.get("content", "") for h in s2.json().get("hits", []))

        bad = client.post(
            "/bi/kf/ingest",
            json={"content": "x", "content_type": "application/pdf"},
            headers={"X-Organisation-Id": "org-api-a", "X-User-Id": "u"},
        )
        assert bad.status_code == 400

        m = client.post(
            "/bi/kf/memory",
            json={"memory_type": "episodic", "content": {"note": "n1"}},
            headers={"X-Organisation-Id": "org-api-a", "X-User-Id": "u"},
        )
        assert m.status_code == 200
        mid = m.json()["memory_id"]
        assert client.get(f"/bi/kf/memory/{mid}", headers={"X-Organisation-Id": "org-api-b", "X-User-Id": "u"}).status_code == 404
        assert client.get(f"/bi/kf/memory/{mid}", headers={"X-Organisation-Id": "org-api-a", "X-User-Id": "u"}).status_code == 200
