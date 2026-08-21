"""Document import and metadata management. Port of ``document-service.ts`` (P06)."""

from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..shared.types import Document
from .logger import logger
from .persistence_service import PersistenceService

SERVICE = "document-service"
DOCUMENTS_META = "documents-meta.json"
MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

_EXT_RE = re.compile(r"\.[^.]+$")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class DocumentService:
    def __init__(self, persistence: PersistenceService) -> None:
        self.persistence = persistence
        self.log = logger.for_service(SERVICE)
        self.log.info("DocumentService initialized")

    def list_documents(self) -> List[Document]:
        """List all imported documents."""
        docs = self.persistence.read_json(DOCUMENTS_META)
        self.log.debug("Listing documents", {"count": len(docs) if docs else 0})
        return docs if docs is not None else []

    def import_document(self, file_path: str) -> Document:
        """Import a file from the given path."""
        self.log.info("Starting document import", {"filePath": file_path})

        if not os.path.exists(file_path):
            self.log.error("File not found during import", {"filePath": file_path})
            raise FileNotFoundError(f"File not found: {file_path}")

        filename = os.path.basename(file_path)
        with open(file_path, "r", encoding="utf-8") as fh:
            content = fh.read()
        size = os.stat(file_path).st_size

        if size > MAX_SIZE_BYTES:
            self.log.error("File exceeds 10MB size limit", {"filePath": file_path, "sizeBytes": size})
            raise ValueError(
                f"File too large: {filename} ({size / 1024 / 1024:.1f} MB). Maximum size is 10 MB."
            )

        doc: Document = {
            "id": str(uuid.uuid4()),
            "title": _EXT_RE.sub("", filename),
            "filename": filename,
            "importedAt": _now_iso(),
            "size": size,
            "status": "imported",
        }

        # Copy file to data directory
        self.persistence.copy_file_to_documents(file_path, filename)

        # Store content for indexing
        self.persistence.write_text(f"content/{doc['id']}.txt", content)

        # Update metadata
        docs = self.list_documents()
        docs.append(doc)
        self.persistence.write_json(DOCUMENTS_META, docs)

        self.log.info(
            "Document imported successfully",
            {
                "documentId": doc["id"],
                "filename": doc["filename"],
                "sizeBytes": doc["size"],
                "contentLength": len(content),
                "totalDocuments": len(docs),
            },
        )
        return doc

    def get_document(self, doc_id: str) -> Optional[Document]:
        """Get a single document by ID."""
        docs = self.list_documents()
        doc = next((d for d in docs if d["id"] == doc_id), None)
        if not doc:
            self.log.warn("Document not found", {"documentId": doc_id})
        return doc

    def get_document_content(self, doc_id: str) -> Optional[str]:
        """Get the text content of a document."""
        return self.persistence.read_text(f"content/{doc_id}.txt")

    def update_document(self, doc_id: str, updates: Dict[str, Any]) -> Optional[Document]:
        """Update a document's metadata."""
        docs = self.list_documents()
        index = next((i for i, d in enumerate(docs) if d["id"] == doc_id), -1)
        if index == -1:
            self.log.warn("Cannot update -- document not found", {"documentId": doc_id})
            return None

        docs[index] = {**docs[index], **updates}
        self.persistence.write_json(DOCUMENTS_META, docs)
        self.log.info("Document metadata updated", {"documentId": doc_id, "updatedFields": list(updates.keys())})
        return docs[index]

    def delete_document(self, doc_id: str) -> bool:
        """Delete a document by ID."""
        docs = self.list_documents()
        doc = next((d for d in docs if d["id"] == doc_id), None)
        if not doc:
            self.log.warn("Cannot delete -- document not found", {"documentId": doc_id})
            return False

        self.persistence.delete_from_documents(doc["filename"])
        # Also remove content file
        content_path = f"content/{doc_id}.txt"
        if self.persistence.exists(content_path):
            self.persistence.write_text(content_path, "")  # Clear content

        updated = [d for d in docs if d["id"] != doc_id]
        self.persistence.write_json(DOCUMENTS_META, updated)

        self.log.info(
            "Document deleted",
            {"documentId": doc_id, "filename": doc["filename"], "remainingDocuments": len(updated)},
        )
        return True

    def has_persisted_data(self) -> bool:
        """Check if any data has been persisted."""
        return self.persistence.exists(DOCUMENTS_META)
