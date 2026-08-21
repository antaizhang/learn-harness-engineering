"""API/route tests using Flask's test client (mirrors the IPC handlers)."""

import io

import pytest

from src.web.app import create_app


@pytest.fixture()
def client(tmp_path):
    app = create_app(data_dir=str(tmp_path / "kb-data"))
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c


def test_index_page_serves(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"Knowledge Base" in res.data


def test_documents_empty(client):
    res = client.get("/api/documents")
    assert res.status_code == 200
    assert res.get_json() == []


def test_import_via_upload_then_index_and_ask(client):
    # Import through a multipart upload.
    data = {
        "file": (io.BytesIO(b"The indexing pipeline splits documents into chunks."), "plan.md"),
    }
    res = client.post("/api/documents/import", data=data, content_type="multipart/form-data")
    assert res.status_code == 200
    doc = res.get_json()
    assert doc["title"] == "plan"

    # It shows up in the list.
    assert len(client.get("/api/documents").get_json()) == 1

    # Index everything.
    status = client.post("/api/indexing/start", json={}).get_json()
    assert status["currentIndexed"] == 1

    # Chunks are retrievable.
    chunks = client.get(f"/api/indexing/chunks/{doc['id']}").get_json()
    assert len(chunks) >= 1

    # Q&A returns a grounded answer with citations.
    ans = client.post("/api/qa/ask", json={"question": "how does indexing chunk documents?"}).get_json()
    assert ans["citations"]
    assert ans["confidence"] == 0.85

    # History persisted.
    hist = client.get("/api/qa/history").get_json()
    assert hist[-1]["question"] == "how does indexing chunk documents?"


def test_import_missing_filepath_returns_400(client):
    res = client.post("/api/documents/import", json={})
    assert res.status_code == 400


def test_delete_document(client):
    data = {"file": (io.BytesIO(b"hello"), "x.txt")}
    doc = client.post("/api/documents/import", data=data, content_type="multipart/form-data").get_json()
    assert client.delete(f"/api/documents/{doc['id']}").get_json() is True
    assert client.get("/api/documents").get_json() == []
