"""Service-layer tests (pytest port of the Vitest suites)."""

import os

import pytest

from src.services.document_service import DocumentService
from src.services.indexing_service import IndexingService
from src.services.persistence_service import PersistenceService
from src.services.qa_service import QaService


@pytest.fixture()
def data_dir(tmp_path):
    return str(tmp_path / "kb-data")


@pytest.fixture()
def persistence(data_dir):
    return PersistenceService(data_dir)


def _write_sample(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return str(p)


# --- PersistenceService ---------------------------------------------------

def test_persistence_creates_directories(persistence, data_dir):
    assert os.path.isdir(data_dir)
    assert os.path.isdir(os.path.join(data_dir, "documents"))
    assert os.path.isdir(os.path.join(data_dir, "index"))


def test_persistence_read_missing_returns_none(persistence):
    assert persistence.read_json("nope.json") is None
    assert persistence.read_text("nope.txt") is None


def test_persistence_json_roundtrip(persistence):
    persistence.write_json("a/b.json", {"x": 1})
    assert persistence.read_json("a/b.json") == {"x": 1}


# --- DocumentService ------------------------------------------------------

def test_import_and_list_document(persistence, tmp_path):
    svc = DocumentService(persistence)
    src = _write_sample(tmp_path, "notes.md", "Hello world")
    doc = svc.import_document(src)

    assert doc["title"] == "notes"
    assert doc["filename"] == "notes.md"
    assert doc["status"] == "imported"
    assert doc["size"] == len("Hello world")
    assert svc.list_documents() == [doc]
    assert svc.get_document(doc["id"]) == doc
    assert svc.get_document_content(doc["id"]) == "Hello world"


def test_import_missing_file_raises(persistence):
    svc = DocumentService(persistence)
    with pytest.raises(FileNotFoundError):
        svc.import_document("/no/such/file.txt")


def test_update_and_delete_document(persistence, tmp_path):
    svc = DocumentService(persistence)
    doc = svc.import_document(_write_sample(tmp_path, "a.txt", "content"))
    updated = svc.update_document(doc["id"], {"status": "indexed", "chunks": 3})
    assert updated["status"] == "indexed"
    assert updated["chunks"] == 3
    assert svc.delete_document(doc["id"]) is True
    assert svc.list_documents() == []
    assert svc.delete_document("missing") is False


def test_delete_removes_stored_content(persistence, tmp_path):
    svc = DocumentService(persistence)
    doc = svc.import_document(_write_sample(tmp_path, "a.txt", "the body"))
    assert svc.get_document_content(doc["id"]) == "the body"
    svc.delete_document(doc["id"])
    assert svc.get_document_content(doc["id"]) is None


def test_has_persisted_data(persistence, tmp_path):
    svc = DocumentService(persistence)
    assert svc.has_persisted_data() is False
    svc.import_document(_write_sample(tmp_path, "a.txt", "x"))
    assert svc.has_persisted_data() is True


# --- IndexingService ------------------------------------------------------

def test_indexing_chunks_and_status(persistence, tmp_path):
    docs = DocumentService(persistence)
    idx = IndexingService(persistence)
    docs.import_document(_write_sample(tmp_path, "d.md", "Para one.\n\nPara two."))

    status = idx.start_indexing()
    assert status["status"] == "ready"
    assert status["currentIndexed"] == 1
    assert status["totalDocuments"] == 1

    chunks = idx.get_all_chunks()
    assert len(chunks) >= 1
    assert chunks[0]["metadata"]["charCount"] == str(len(chunks[0]["content"]))


def test_chunking_splits_large_content(persistence, tmp_path):
    docs = DocumentService(persistence)
    idx = IndexingService(persistence)
    # Several long paragraphs so that chunking must split at ~500 chars.
    para = "word " * 120  # ~600 chars
    content = "\n\n".join([para.strip()] * 4)
    doc = docs.import_document(_write_sample(tmp_path, "big.txt", content))
    idx.start_indexing()
    chunks = idx.get_chunks_for_document(doc["id"])
    assert len(chunks) > 1
    # Every chunk must be non-empty (guards the P4 seeded-bug territory).
    assert all(c["content"].strip() for c in chunks)


def test_index_single_document(persistence, tmp_path):
    docs = DocumentService(persistence)
    idx = IndexingService(persistence)
    doc = docs.import_document(_write_sample(tmp_path, "s.txt", "Only one paragraph here."))
    idx.start_indexing(doc["id"])
    assert len(idx.get_chunks_for_document(doc["id"])) == 1


# --- QaService ------------------------------------------------------------

def test_qa_without_index_has_low_confidence(persistence):
    qa = QaService(persistence)
    # A question with no keyword-pattern match falls back and, with no index,
    # reports the "nothing indexed yet" message at low confidence.
    resp = qa.ask("What time is it?")
    assert resp["citations"] == []
    assert resp["confidence"] == 0.3
    assert "No relevant documents" in resp["answer"]


def test_qa_matches_mock_pattern_without_citations(persistence):
    # A keyword-matching question still returns the mock answer even with no
    # index, but confidence stays low because there are no citations.
    qa = QaService(persistence)
    resp = qa.ask("What is the design?")
    assert resp["citations"] == []
    assert resp["confidence"] == 0.3
    assert "layered architecture" in resp["answer"]


def test_qa_with_index_produces_citations(persistence, tmp_path):
    docs = DocumentService(persistence)
    idx = IndexingService(persistence)
    qa = QaService(persistence, idx)
    docs.import_document(
        _write_sample(
            tmp_path,
            "design-notes.md",
            "The system uses a layered architecture with clear boundaries "
            "between the main process and the renderer. Design patterns matter.",
        )
    )
    idx.start_indexing()
    resp = qa.ask("Tell me about the design architecture")
    assert len(resp["citations"]) >= 1
    assert resp["confidence"] == 0.85
    history = qa.get_history()
    assert history[-1]["question"] == "Tell me about the design architecture"
