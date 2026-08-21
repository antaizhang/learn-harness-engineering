"""Document chunking and index status. Port of ``indexing-service.ts``."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from typing import Any

from ..shared.types import AppStatus, Chunk, IndexStatus
from .persistence_service import PersistenceService

INDEX_META = "index-meta.json"
CHUNKS_DIR = "chunks"

_PARAGRAPH_RE = re.compile(r"\n\s*\n")
_WHITESPACE_RE = re.compile(r"\s+")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class IndexingService:
    def __init__(self, persistence: PersistenceService, document_service: Any = None) -> None:
        self.persistence = persistence
        self.document_service = document_service

    def start_indexing(self, document_id: Optional[str] = None) -> IndexStatus:
        """Start indexing documents. If ``document_id`` is given, index only that one."""
        status = self.get_status()

        if document_id:
            # Index a single document
            content = self.persistence.read_text(f"content/{document_id}.txt")
            if not content:
                return {**status, "status": "error"}
            chunks = self._chunk_document(document_id, content)
            self.persistence.write_json(f"{CHUNKS_DIR}/{document_id}.json", chunks)

            # Update document status to indexed
            if self.document_service:
                self.document_service.update_document(
                    document_id, {"status": "indexed", "chunks": len(chunks)}
                )

            # Update index meta
            chunks_meta: Dict[str, List[str]] = self.persistence.read_json(INDEX_META) or {}
            chunks_meta[document_id] = [c["id"] for c in chunks]
            self.persistence.write_json(INDEX_META, chunks_meta)

            return self.get_status()

        # Index all documents that haven't been indexed yet
        docs_meta = self.persistence.read_json("documents-meta.json") or []
        chunks_meta = self.persistence.read_json(INDEX_META) or {}

        for doc in docs_meta:
            if doc["id"] in chunks_meta:
                continue

            content = self.persistence.read_text(f"content/{doc['id']}.txt")
            if not content:
                continue

            chunks = self._chunk_document(doc["id"], content)
            self.persistence.write_json(f"{CHUNKS_DIR}/{doc['id']}.json", chunks)
            chunks_meta[doc["id"]] = [c["id"] for c in chunks]

            # Update document status to indexed
            if self.document_service:
                self.document_service.update_document(
                    doc["id"], {"status": "indexed", "chunks": len(chunks)}
                )

        self.persistence.write_json(INDEX_META, chunks_meta)
        return self.get_status()

    def get_status(self) -> IndexStatus:
        """Get current indexing status including chunk counts."""
        docs = self.persistence.read_json("documents-meta.json") or []
        chunks_meta = self.persistence.read_json(INDEX_META) or {}

        current_indexed = len(chunks_meta.keys())
        total_documents = len(docs)
        is_ready = current_indexed == total_documents and total_documents > 0

        # Count total chunks across all indexed documents
        total_chunks = 0
        for doc_id in chunks_meta.keys():
            total_chunks += len(self.get_chunks_for_document(doc_id))

        return {
            "status": "ready" if is_ready else ("indexing" if current_indexed > 0 else "idle"),
            "currentIndexed": current_indexed,
            "totalDocuments": total_documents,
            "lastIndexed": _now_iso(),
            "totalChunks": total_chunks,
        }

    def get_app_status(self) -> AppStatus:
        """Get app status for the renderer."""
        index_status = self.get_status()
        return {
            "documentsLoaded": index_status["totalDocuments"],
            "indexStatus": index_status["status"],
            "lastActivity": index_status["lastIndexed"] or "",
            "indexedCount": index_status["currentIndexed"],
            "totalChunks": index_status["totalChunks"],
        }

    def get_chunks_for_document(self, document_id: str) -> List[Chunk]:
        """Get all chunks for a document."""
        return self.persistence.read_json(f"{CHUNKS_DIR}/{document_id}.json") or []

    def get_all_chunks(self) -> List[Chunk]:
        """Get all chunks across all documents."""
        chunks_meta = self.persistence.read_json(INDEX_META) or {}
        all_chunks: List[Chunk] = []

        for doc_id in chunks_meta.keys():
            all_chunks.extend(self.get_chunks_for_document(doc_id))

        return all_chunks

    def _chunk_document(self, document_id: str, content: str) -> List[Chunk]:
        """Split a document into chunks of ~500 characters at paragraph boundaries."""
        CHUNK_SIZE = 500
        chunks: List[Chunk] = []

        # Split on double newlines (paragraphs)
        paragraphs = [p for p in _PARAGRAPH_RE.split(content) if p.strip()]

        buffer = ""
        chunk_index = 0

        for para in paragraphs:
            if len(buffer) + len(para) > CHUNK_SIZE and len(buffer) > 0:
                chunks.append(self._create_chunk(document_id, chunk_index, buffer.strip()))
                chunk_index += 1
                buffer = para
            else:
                buffer += ("\n\n" if buffer else "") + para

        if buffer.strip():
            chunks.append(self._create_chunk(document_id, chunk_index, buffer.strip()))

        return chunks

    def _create_chunk(self, document_id: str, index: int, content: str) -> Chunk:
        return {
            "id": str(uuid.uuid4()),
            "documentId": document_id,
            "content": content,
            "index": index,
            "metadata": {
                "charCount": str(len(content)),
                "wordCount": str(len(_WHITESPACE_RE.split(content))),
            },
        }
