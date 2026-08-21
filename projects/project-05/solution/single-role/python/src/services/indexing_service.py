"""Document chunking and index status. Port of ``indexing-service.ts``."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..shared.types import Chunk, IndexStatus
from .logger import logger
from .persistence_service import PersistenceService

INDEX_META = "index-meta.json"
CHUNKS_DIR = "chunks"

_PARAGRAPH_RE = re.compile(r"\n\s*\n")
_WHITESPACE_RE = re.compile(r"\s+")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class IndexingService:
    def __init__(self, persistence: PersistenceService) -> None:
        self.persistence = persistence
        self.log = logger.for_service("IndexingService")
        self.log.info("IndexingService constructed")

    def start_indexing(self, document_id: Optional[str] = None) -> IndexStatus:
        """Start indexing documents. If ``document_id`` is given, index only that one."""
        self.log.info("startIndexing called", {"documentId": document_id or "all"})
        status = self.get_status()

        if document_id:
            # Index a single document
            content = self.persistence.read_text(f"content/{document_id}.txt")
            if not content:
                self.log.error("Document content not found", {"documentId": document_id})
                return {**status, "status": "error"}
            self.log.info(
                "Indexing single document",
                {"documentId": document_id, "contentLength": len(content)},
            )
            chunks = self._chunk_document(document_id, content)
            self.persistence.write_json(f"{CHUNKS_DIR}/{document_id}.json", chunks)
            self.log.info(
                "Single document indexed",
                {"documentId": document_id, "chunkCount": len(chunks)},
            )
            return self.get_status()

        # Index all documents that haven't been indexed yet
        docs_meta = self.persistence.read_json("documents-meta.json") or []
        chunks_meta: Dict[str, List[str]] = self.persistence.read_json(INDEX_META) or {}

        self.log.info(
            "Batch indexing starting",
            {"totalDocs": len(docs_meta), "alreadyIndexed": len(chunks_meta)},
        )

        for doc in docs_meta:
            if doc["id"] in chunks_meta:
                continue

            content = self.persistence.read_text(f"content/{doc['id']}.txt")
            if not content:
                self.log.warn(
                    "Skipping document with no content",
                    {"docId": doc["id"], "title": doc.get("title")},
                )
                continue

            self.log.info(
                "Indexing document",
                {"docId": doc["id"], "title": doc.get("title"), "contentLength": len(content)},
            )
            chunks = self._chunk_document(doc["id"], content)
            self.persistence.write_json(f"{CHUNKS_DIR}/{doc['id']}.json", chunks)
            chunks_meta[doc["id"]] = [c["id"] for c in chunks]
            self.log.info("Document indexed", {"docId": doc["id"], "chunkCount": len(chunks)})

        self.persistence.write_json(INDEX_META, chunks_meta)
        self.log.info("Batch indexing complete")
        return self.get_status()

    def get_status(self) -> IndexStatus:
        """Get current indexing status."""
        docs = self.persistence.read_json("documents-meta.json") or []
        chunks_meta = self.persistence.read_json(INDEX_META) or {}

        current_indexed = len(chunks_meta.keys())
        total_documents = len(docs)
        is_ready = current_indexed == total_documents and total_documents > 0

        return {
            "status": "ready" if is_ready else ("indexing" if current_indexed > 0 else "idle"),
            "currentIndexed": current_indexed,
            "totalDocuments": total_documents,
            "lastIndexed": _now_iso(),
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

        self.log.info(
            "chunkDocument",
            {
                "documentId": document_id,
                "contentLength": len(content),
                "paragraphCount": len(paragraphs),
            },
        )

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

        self.log.info(
            "chunkDocument complete",
            {
                "documentId": document_id,
                "totalChunks": len(chunks),
                "totalChars": sum(len(c["content"]) for c in chunks),
            },
        )

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
