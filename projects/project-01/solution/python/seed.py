"""Convenience seeder: import the bundled sample documents and index them.

    python seed.py

Useful because the in-app Import button is a stub in Project 01 (a real desktop
app would open a file dialog). Uses the same services the web API uses.
"""

import os

from src.services.document_service import DocumentService
from src.services.indexing_service import IndexingService
from src.services.persistence_service import PersistenceService
from src.web.app import _default_data_dir

SAMPLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sample-documents")


def main() -> None:
    data_dir = os.environ.get("KB_DATA_DIR") or _default_data_dir()
    persistence = PersistenceService(data_dir)
    documents = DocumentService(persistence)
    indexing = IndexingService(persistence)

    existing = {d["filename"] for d in documents.list_documents()}
    imported = 0
    for name in sorted(os.listdir(SAMPLES_DIR)):
        if name in existing:
            continue
        documents.import_document(os.path.join(SAMPLES_DIR, name))
        imported += 1

    status = indexing.start_indexing()
    print(f"Imported {imported} new document(s); data dir: {data_dir}")
    print(f"Index status: {status['status']} ({status['currentIndexed']}/{status['totalDocuments']})")


if __name__ == "__main__":
    main()
