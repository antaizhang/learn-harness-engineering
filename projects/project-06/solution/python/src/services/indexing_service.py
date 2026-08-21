"""Document chunking and index status. Port of ``indexing-service.ts`` (P06)."""

from __future__ import annotations

import re
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..shared.types import Chunk, IndexStatus
from .logger import logger
from .persistence_service import PersistenceService

SERVICE = "indexing-service"
INDEX_META = "index-meta.json"
CHUNKS_DIR = "chunks"

_PARAGRAPH_RE = re.compile(r"\n\s*\n")
_WHITESPACE_RE = re.compile(r"\s+")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class IndexingService:
    def __init__(self, persistence: PersistenceService) -> None:
        self.persistence = persistence
        self.log = logger.for_service(SERVICE)
        self.log.info("IndexingService initialized")

    def start_indexing(self, document_id: Optional[str] = None) -> IndexStatus:
        """Start indexing documents. If ``document_id`` is given, index only that one."""
        start_time = time.monotonic()
        self.log.info("Indexing started", {"documentId": document_id or "all"})

        status = self.get_status()

        if document_id:
            content = self.persistence.read_text(f"content/{document_id}.txt")
            if not content:
                self.log.error("Content not found for single document indexing", {"documentId": document_id})
                return {**status, "status": "error"}
            chunks = self._chunk_document(document_id, content)
            self.persistence.write_json(f"{CHUNKS_DIR}/{document_id}.json", chunks)

            # Update document status to indexed
            docs_meta = self.persistence.read_json("documents-meta.json") or []
            for doc in docs_meta:
                if doc["id"] == document_id:
                    doc["status"] = "indexed"
                    doc["chunks"] = len(chunks)
                    self.persistence.write_json("documents-meta.json", docs_meta)
                    break

            # Update index meta so the chunks count toward status/retrieval
            chunks_meta: Dict[str, List[str]] = self.persistence.read_json(INDEX_META) or {}
            chunks_meta[document_id] = [c["id"] for c in chunks]
            self.persistence.write_json(INDEX_META, chunks_meta)

            duration_ms = int((time.monotonic() - start_time) * 1000)
            self.log.info(
                "Single document indexed",
                {
                    "documentId": document_id,
                    "chunkCount": len(chunks),
                    "contentLength": len(content),
                    "durationMs": duration_ms,
                },
            )
            return self.get_status()

        # Index all documents that haven't been indexed yet
        docs_meta = self.persistence.read_json("documents-meta.json") or []
        chunks_meta = self.persistence.read_json(INDEX_META) or {}

        indexed_count = 0
        total_chunks = 0

        for doc in docs_meta:
            if doc["id"] in chunks_meta:
                continue

            content = self.persistence.read_text(f"content/{doc['id']}.txt")
            if not content:
                self.log.warn("Skipping document -- content not found", {"documentId": doc["id"]})
                continue

            chunks = self._chunk_document(doc["id"], content)
            self.persistence.write_json(f"{CHUNKS_DIR}/{doc['id']}.json", chunks)
            chunks_meta[doc["id"]] = [c["id"] for c in chunks]
            total_chunks += len(chunks)
            indexed_count += 1

            doc["status"] = "indexed"
            doc["chunks"] = len(chunks)

            self.log.info(
                "Document indexed in batch",
                {
                    "documentId": doc["id"],
                    "filename": doc.get("filename"),
                    "chunkCount": len(chunks),
                    "progress": f"{indexed_count}/{len(docs_meta)}",
                },
            )

        self.persistence.write_json(INDEX_META, chunks_meta)
        self.persistence.write_json("documents-meta.json", docs_meta)

        duration_ms = int((time.monotonic() - start_time) * 1000)
        throughput = (
            f"{total_chunks / (duration_ms / 1000):.1f} chunks/sec" if total_chunks > 0 and duration_ms > 0 else "N/A"
        )
        self.log.info(
            "Batch indexing complete",
            {
                "totalDocs": len(docs_meta),
                "newlyIndexed": indexed_count,
                "totalChunks": total_chunks,
                "durationMs": duration_ms,
                "throughput": throughput,
            },
        )
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
        chunks = self.persistence.read_json(f"{CHUNKS_DIR}/{document_id}.json") or []
        self.log.debug("Retrieved chunks for document", {"documentId": document_id, "chunkCount": len(chunks)})
        return chunks

    def get_all_chunks(self) -> List[Chunk]:
        """Get all chunks across all documents."""
        chunks_meta = self.persistence.read_json(INDEX_META) or {}
        all_chunks: List[Chunk] = []
        for doc_id in chunks_meta.keys():
            all_chunks.extend(self.get_chunks_for_document(doc_id))
        self.log.debug("Retrieved all chunks", {"totalChunks": len(all_chunks)})
        return all_chunks

    def _chunk_document(self, document_id: str, content: str) -> List[Chunk]:
        """Split a document into chunks of ~500 characters at paragraph boundaries."""
        CHUNK_SIZE = 500
        chunks: List[Chunk] = []

        paragraphs = [p for p in _PARAGRAPH_RE.split(content) if p.strip()]
        self.log.debug("Chunking document", {"documentId": document_id, "paragraphCount": len(paragraphs)})

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
