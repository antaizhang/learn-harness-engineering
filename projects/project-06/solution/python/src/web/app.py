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
from ..services.logger import logger
from ..services.persistence_service import PersistenceService
from ..services.qa_service import QaService
from ..shared.types import IPC_CHANNELS

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
    app_log = logger.for_service("App")
    app_log.info("Starting service initialization")
    resolved_data_dir = data_dir or _default_data_dir()
    app_log.info("Data directory resolved", {"dataDir": resolved_data_dir})
    persistence = PersistenceService(resolved_data_dir)
    app_log.info("PersistenceService initialized")
    document_service = DocumentService(persistence)
    app_log.info("DocumentService initialized")
    indexing_service = IndexingService(persistence)
    app_log.info("IndexingService initialized")
    qa_service = QaService(persistence, indexing_service)
    app_log.info("QaService initialized")

    ipc_log = logger.for_service("ipc-handlers")

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
        ipc_log.info("LIST_DOCUMENTS")
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
            ipc_log.info("IMPORT_DOCUMENT", {"filePath": upload.filename})
            suffix = os.path.splitext(upload.filename)[1]
            fd, tmp_path = tempfile.mkstemp(suffix=suffix)
            os.close(fd)
            try:
                upload.save(tmp_path)
                # Preserve the original filename for metadata/title.
                final_path = os.path.join(os.path.dirname(tmp_path), upload.filename)
                os.replace(tmp_path, final_path)
                doc = document_service.import_document(final_path)
                ipc_log.info(
                    "Document imported",
                    {"id": doc["id"], "title": doc["title"], "size": doc["size"]},
                )
            except Exception as err:  # noqa: BLE001 -- mirror the TS log-and-rethrow
                ipc_log.error("Document import failed", {"filePath": upload.filename, "error": str(err)})
                raise
            finally:
                for p in (tmp_path, locals().get("final_path", "")):
                    if p and os.path.exists(p):
                        os.unlink(p)
            return jsonify(doc)

        body = request.get_json(silent=True) or {}
        file_path = body.get("filePath")
        if not file_path:
            return jsonify({"error": "No file or filePath provided"}), 400
        ipc_log.info("IMPORT_DOCUMENT", {"filePath": file_path})
        try:
            doc = document_service.import_document(file_path)
            ipc_log.info("Document imported", {"id": doc["id"], "title": doc["title"], "size": doc["size"]})
        except FileNotFoundError as exc:
            ipc_log.error("Document import failed", {"filePath": file_path, "error": str(exc)})
            return jsonify({"error": str(exc)}), 404
        return jsonify(doc)

    @app.get("/api/documents/<doc_id>")
    def get_document(doc_id: str):
        ipc_log.info("GET_DOCUMENT", {"id": doc_id})
        return jsonify(document_service.get_document(doc_id))

    @app.delete("/api/documents/<doc_id>")
    def delete_document(doc_id: str):
        ipc_log.info("DELETE_DOCUMENT", {"id": doc_id})
        return jsonify(document_service.delete_document(doc_id))

    # --- Indexing (IPC: indexing:*) ---
    @app.post("/api/indexing/start")
    def start_indexing():
        body = request.get_json(silent=True) or {}
        document_id = body.get("documentId")
        ipc_log.info("START_INDEXING", {"documentId": document_id or "all"})
        try:
            status = indexing_service.start_indexing(document_id)
            ipc_log.info(
                "Indexing complete",
                {
                    "status": status["status"],
                    "indexed": status["currentIndexed"],
                    "total": status["totalDocuments"],
                },
            )
        except Exception as err:  # noqa: BLE001
            ipc_log.error("Indexing failed", {"documentId": document_id, "error": str(err)})
            raise
        return jsonify(status)

    @app.get("/api/indexing/status")
    def indexing_status():
        return jsonify(indexing_service.get_status())

    @app.get("/api/indexing/chunks/<doc_id>")
    def get_chunks(doc_id: str):
        ipc_log.info("GET_CHUNKS", {"documentId": doc_id})
        return jsonify(indexing_service.get_chunks_for_document(doc_id))

    # --- Q&A (IPC: qa:*) ---
    @app.post("/api/qa/ask")
    def ask_question():
        body = request.get_json(silent=True) or {}
        question = body.get("question", "")
        ipc_log.info("ASK_QUESTION", {"question": question})
        try:
            response = qa_service.ask(question)
            ipc_log.info(
                "Q&A response",
                {"confidence": response["confidence"], "citationCount": len(response["citations"])},
            )
        except Exception as err:  # noqa: BLE001
            ipc_log.error("Q&A failed", {"question": question, "error": str(err)})
            raise
        return jsonify(response)

    @app.get("/api/qa/history")
    def qa_history():
        ipc_log.debug("GET_HISTORY")
        return jsonify(qa_service.get_history())

    @app.post("/api/qa/clear-history")
    def clear_history():
        ipc_log.info("CLEAR_HISTORY")
        qa_service.clear_history()
        return jsonify(None)

    # --- Feedback (IPC: feedback:*) ---
    @app.post("/api/feedback")
    def submit_feedback():
        body = request.get_json(silent=True) or {}
        qa_timestamp = body.get("qaTimestamp", "")
        question = body.get("question", "")
        rating = body.get("rating", "positive")
        comment = body.get("comment", "")
        ipc_log.info("SUBMIT_FEEDBACK", {"qaTimestamp": qa_timestamp, "rating": rating})
        return jsonify(qa_service.submit_feedback(qa_timestamp, question, rating, comment))

    @app.get("/api/feedback")
    def list_feedback():
        ipc_log.debug("GET_FEEDBACK")
        return jsonify(qa_service.get_feedback())

    # --- Clean state (IPC: app:reset) ---
    @app.post("/api/reset")
    def reset_data():
        ipc_log.warn("RESET_DATA -- resetting all application data")
        persistence.reset_all()
        return jsonify({"success": True})

    app_log.info(
        "All IPC handlers registered", {"channels": len(IPC_CHANNELS)}
    )

    return app
