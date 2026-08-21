"""Document import and metadata management. Port of ``document-service.ts``."""

from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..shared.types import Document
from .persistence_service import PersistenceService

DOCUMENTS_META = "documents-meta.json"

_EXT_RE = re.compile(r"\.[^.]+$")


def _now_iso() -> str:
    """ISO-8601 timestamp with a trailing 'Z', matching JS ``toISOString()``."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class DocumentService:
    def __init__(self, persistence: PersistenceService) -> None:
        self.persistence = persistence

    def list_documents(self) -> List[Document]:
        """List all imported documents."""
        docs = self.persistence.read_json(DOCUMENTS_META)
        return docs if docs is not None else []

    def import_document(self, file_path: str) -> Document:
        """Import a file from the given path."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        filename = os.path.basename(file_path)
        with open(file_path, "r", encoding="utf-8") as fh:
            content = fh.read()
        size = os.stat(file_path).st_size

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

        # Store content for indexing and viewing
        self.persistence.write_text(f"content/{doc['id']}.txt", content)

        # Update metadata
        docs = self.list_documents()
        docs.append(doc)
        self.persistence.write_json(DOCUMENTS_META, docs)

        return doc

    def get_document(self, doc_id: str) -> Optional[Document]:
        """Get a single document by ID."""
        docs = self.list_documents()
        return next((d for d in docs if d["id"] == doc_id), None)

    def get_document_content(self, doc_id: str) -> Optional[str]:
        """Get the text content of a document."""
        return self.persistence.read_text(f"content/{doc_id}.txt")

    def update_document(self, doc_id: str, updates: Dict[str, Any]) -> Optional[Document]:
        """Update a document's metadata."""
        docs = self.list_documents()
        index = next((i for i, d in enumerate(docs) if d["id"] == doc_id), -1)
        if index == -1:
            return None

        docs[index] = {**docs[index], **updates}
        self.persistence.write_json(DOCUMENTS_META, docs)
        return docs[index]

    def delete_document(self, doc_id: str) -> bool:
        """Delete a document by ID. Removes content and metadata."""
        docs = self.list_documents()
        doc = next((d for d in docs if d["id"] == doc_id), None)
        if not doc:
            return False

        # Remove file from documents directory
        self.persistence.delete_from_documents(doc["filename"])

        # Remove stored content
        content_path = os.path.join(self.persistence.get_data_dir(), "content", f"{doc_id}.txt")
        if os.path.exists(content_path):
            os.unlink(content_path)

        # Update metadata
        updated = [d for d in docs if d["id"] != doc_id]
        self.persistence.write_json(DOCUMENTS_META, updated)
        return True

    def has_persisted_data(self) -> bool:
        """Check whether the persistence layer has stored data."""
        return self.persistence.exists(DOCUMENTS_META)
