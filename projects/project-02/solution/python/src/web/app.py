"""Flask application factory -- the Python web equivalent of the Electron shell.

Architecture mapping from the original Electron/TypeScript app:

* ``src/main/main.ts``          -> :func:`create_app` (process/window bootstrap)
* ``src/main/ipc-handlers.ts``  -> the ``/api/*`` routes registered below
* ``src/preload/preload.ts``    -> the ``knowledgeBase`` client in ``static/app.js``
* ``src/renderer`` (React)      -> ``templates/index.html`` + ``static/app.js``

The service layer is a direct port and is reused unchanged.
"""

from __future__ import annotations

import os
import tempfile
from typing import Optional

from flask import Flask, jsonify, render_template, request

from ..services.document_service import DocumentService
from ..services.indexing_service import IndexingService
from ..services.persistence_service import PersistenceService
from ..services.qa_service import QaService

# python/ project root (three levels up from this file: src/web/app.py)
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _default_data_dir() -> str:
    """Where application data lives.

    Mirrors the Electron ``userData/knowledge-base-data`` location. Overridable
    via the ``KB_DATA_DIR`` environment variable (and by tests).
    """
    env = os.environ.get("KB_DATA_DIR")
    if env:
        return env
    return os.path.join(_ROOT, ".kb-data", "knowledge-base-data")


def create_app(data_dir: Optional[str] = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=os.path.join(_ROOT, "templates"),
        static_folder=os.path.join(_ROOT, "static"),
    )

    # --- Initialize services (mirrors main.ts initializeServices) ---
    resolved_data_dir = data_dir or _default_data_dir()
    persistence = PersistenceService(resolved_data_dir)
    document_service = DocumentService(persistence)
    indexing_service = IndexingService(persistence)
    qa_service = QaService(persistence, indexing_service)

    app.config["PERSISTENCE"] = persistence
    app.config["DOCUMENT_SERVICE"] = document_service
    app.config["INDEXING_SERVICE"] = indexing_service
    app.config["QA_SERVICE"] = qa_service

    # --- Renderer entry point ---
    @app.get("/")
    def index():
        return render_template("index.html")

    # --- Document operations (IPC: documents:*) ---
    @app.get("/api/documents")
    def list_documents():
        return jsonify(document_service.list_documents())

    @app.post("/api/documents/import")
    def import_document():
        """Import a document.

        Two ways in, mirroring how the Electron app could be driven:
        * a ``filePath`` in a JSON body (the console/IPC path used in P1), or
        * a multipart ``file`` upload (used by later projects' Import panel).
        """
        upload = request.files.get("file")
        if upload is not None and upload.filename:
            suffix = os.path.splitext(upload.filename)[1]
            fd, tmp_path = tempfile.mkstemp(suffix=suffix)
            os.close(fd)
            try:
                upload.save(tmp_path)
                # Preserve the original filename for metadata/title.
                final_path = os.path.join(os.path.dirname(tmp_path), upload.filename)
                os.replace(tmp_path, final_path)
                doc = document_service.import_document(final_path)
            finally:
                for p in (tmp_path, locals().get("final_path", "")):
                    if p and os.path.exists(p):
                        os.unlink(p)
            return jsonify(doc)

        body = request.get_json(silent=True) or {}
        file_path = body.get("filePath")
        if not file_path:
            return jsonify({"error": "No file or filePath provided"}), 400
        try:
            doc = document_service.import_document(file_path)
        except FileNotFoundError as exc:
            return jsonify({"error": str(exc)}), 404
        return jsonify(doc)

    @app.get("/api/documents/<doc_id>")
    def get_document(doc_id: str):
        return jsonify(document_service.get_document(doc_id))

    @app.get("/api/documents/<doc_id>/content")
    def get_document_content(doc_id: str):
        return jsonify(document_service.get_document_content(doc_id))

    @app.delete("/api/documents/<doc_id>")
    def delete_document(doc_id: str):
        return jsonify(document_service.delete_document(doc_id))

    # --- Indexing (IPC: indexing:*) ---
    @app.post("/api/indexing/start")
    def start_indexing():
        body = request.get_json(silent=True) or {}
        document_id = body.get("documentId")
        return jsonify(indexing_service.start_indexing(document_id))

    @app.get("/api/indexing/status")
    def indexing_status():
        return jsonify(indexing_service.get_status())

    @app.get("/api/indexing/chunks/<doc_id>")
    def get_chunks(doc_id: str):
        return jsonify(indexing_service.get_chunks_for_document(doc_id))

    # --- Q&A (IPC: qa:*) ---
    @app.post("/api/qa/ask")
    def ask_question():
        body = request.get_json(silent=True) or {}
        question = body.get("question", "")
        return jsonify(qa_service.ask(question))

    @app.get("/api/qa/history")
    def qa_history():
        return jsonify(qa_service.get_history())

    return app
