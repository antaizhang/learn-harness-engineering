"""Cross-boundary type definitions shared between the web app, API layer, and services.

Port of ``src/shared/types.ts`` (Project 06 capstone). Data is carried as plain
dicts, matching the plain objects in the original TypeScript app so JSON
persistence stays compatible.
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional, TypedDict

DocumentStatus = Literal["imported", "indexing", "indexed", "error"]
IndexStatusState = Literal["idle", "indexing", "ready", "error"]
FeedbackRating = Literal["positive", "negative"]
ConversationRole = Literal["user", "assistant"]


class Document(TypedDict, total=False):
    id: str
    title: str
    filename: str
    importedAt: str
    size: int
    status: DocumentStatus
    chunks: int  # optional -- set once the document has been indexed


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


class FeedbackEntry(TypedDict):
    id: str
    qaTimestamp: str
    question: str
    rating: FeedbackRating
    comment: str
    submittedAt: str


class ConversationMessage(TypedDict, total=False):
    id: str
    role: ConversationRole
    content: str
    timestamp: str
    citations: List[Citation]
    confidence: float
    followUpSuggestions: List[str]


class AppStatus(TypedDict, total=False):
    documentsLoaded: int
    currentIndexed: int
    indexStatus: IndexStatusState
    lastActivity: str


class IndexStatus(TypedDict):
    status: IndexStatusState
    currentIndexed: int
    totalDocuments: int
    lastIndexed: Optional[str]


# --- IPC channel names -- single source of truth. -------------------------
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
    # Feedback
    "SUBMIT_FEEDBACK": "feedback:submit",
    "GET_FEEDBACK": "feedback:list",
    # Clean state
    "RESET_DATA": "app:reset",
    # App status
    "GET_STATUS": "app:status",
}
