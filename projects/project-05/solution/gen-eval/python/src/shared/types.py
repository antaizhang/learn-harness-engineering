"""Cross-boundary type definitions shared between the web app, API layer, and services.

This mirrors ``src/shared/types.ts`` from the Electron/TypeScript version. In the
TypeScript app these were structural interfaces; in Python we express the same
shapes as ``TypedDict`` definitions plus small factory helpers. The data is still
carried around as plain dicts (exactly like the plain objects used in the TS code),
which keeps JSON persistence byte-for-byte compatible with the original app.
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional, TypedDict

# --- Domain types ---------------------------------------------------------

DocumentStatus = Literal["imported", "indexing", "indexed", "error"]
IndexStatusState = Literal["idle", "indexing", "ready", "error"]


class Document(TypedDict, total=False):
    id: str
    title: str
    filename: str
    importedAt: str
    size: int
    status: DocumentStatus
    chunks: int  # optional -- omitted until the document has been indexed


class Chunk(TypedDict):
    id: str
    documentId: str
    content: str
    index: int
    metadata: Dict[str, str]


class Citation(TypedDict):
    documentId: str
    documentTitle: str
    chunkIndex: int
    excerpt: str


class QAResponse(TypedDict):
    answer: str
    citations: List[Citation]
    confidence: float
    timestamp: str


class QAHistory(TypedDict):
    question: str
    response: QAResponse


ConversationRole = Literal["user", "assistant"]


class ConversationMessage(TypedDict, total=False):
    id: str
    role: ConversationRole
    content: str
    timestamp: str
    citations: List[Citation]
    confidence: float
    followUpSuggestions: List[str]


class AppStatus(TypedDict):
    documentsLoaded: int
    indexStatus: IndexStatusState
    lastActivity: str


class IndexStatus(TypedDict):
    status: IndexStatusState
    currentIndexed: int
    totalDocuments: int
    lastIndexed: Optional[str]


# --- IPC channel names -- single source of truth. -------------------------
# In the Electron app these named the ipcRenderer.invoke channels. Here they
# double as stable identifiers and map one-to-one onto the HTTP API routes
# registered in ``src/web/app.py``.
IPC_CHANNELS: Dict[str, str] = {
    # Document operations
    "LIST_DOCUMENTS": "documents:list",
    "IMPORT_DOCUMENT": "documents:import",
    "GET_DOCUMENT": "documents:get",
    "DELETE_DOCUMENT": "documents:delete",
    # Indexing
    "START_INDEXING": "indexing:start",
    "GET_INDEXING_STATUS": "indexing:status",
    "GET_CHUNKS": "indexing:chunks",
    # Q&A
    "ASK_QUESTION": "qa:ask",
    "GET_HISTORY": "qa:history",
    "CLEAR_HISTORY": "qa:clear-history",
    # Conversation
    "GET_CONVERSATION": "conversation:get",
    # App status
    "GET_STATUS": "app:status",
}
