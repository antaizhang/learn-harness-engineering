"""Mock grounded Q&A with citations + feedback. Port of ``qa-service.ts`` (P06)."""

from __future__ import annotations

import random
import re
import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from ..shared.types import Citation, FeedbackEntry, FeedbackRating, QAHistory, QAResponse
from .indexing_service import IndexingService
from .logger import logger
from .persistence_service import PersistenceService

SERVICE = "qa-service"
QA_HISTORY_FILE = "qa-history.json"
FEEDBACK_FILE = "feedback.json"

_WHITESPACE_RE = re.compile(r"\s+")

# Mock Q&A patterns keyed to document content keywords.
MOCK_PATTERNS = [
    {
        "keywords": ["design", "architecture", "pattern"],
        "answer": "The system uses a layered architecture with clear boundaries between the main process, preload scripts, and renderer. Each layer communicates through typed IPC channels, and the services layer handles business logic independently of the UI.",
        "excerpt": "The system uses a layered architecture with clear boundaries",
    },
    {
        "keywords": ["import", "document", "file"],
        "answer": "Documents are imported by copying the source file to the local data directory. The system extracts text content and creates metadata including title, filename, size, and import timestamp. After import, documents can be indexed for search.",
        "excerpt": "Documents are imported by copying the source file",
    },
    {
        "keywords": ["index", "chunk", "search"],
        "answer": "The indexing pipeline splits documents into chunks of approximately 500 characters at paragraph boundaries. Each chunk includes metadata like character count and word count. The index enables grounded Q&A with citations pointing to specific document sections.",
        "excerpt": "The indexing pipeline splits documents into chunks",
    },
    {
        "keywords": ["retrieval", "search", "query"],
        "answer": "Retrieval works by matching query keywords against indexed chunks. The system ranks chunks by keyword overlap and returns the most relevant excerpts as citations alongside the generated answer.",
        "excerpt": "Retrieval works by matching query keywords against indexed chunks",
    },
    {
        "keywords": ["meeting", "notes", "summary"],
        "answer": "The meeting summary indicates that the team discussed implementing a retrieval-augmented generation pipeline. Key decisions included using local chunk storage and citation-based verification to ensure answer accuracy.",
        "excerpt": "The team discussed implementing a retrieval-augmented generation pipeline",
    },
    {
        "keywords": ["logging", "debug", "observe", "monitor"],
        "answer": "The application uses structured JSON logging throughout all services. Each log entry includes a timestamp, log level, service name, and optional data payload. This enables runtime observability and debugging of the full document lifecycle.",
        "excerpt": "The application uses structured JSON logging throughout all services",
    },
    {
        "keywords": ["feedback", "rating", "quality"],
        "answer": "Users can provide positive or negative feedback on Q&A responses. Feedback is stored alongside the question and answer in a dedicated feedback log. This data can be used to improve answer quality over time.",
        "excerpt": "Users can provide positive or negative feedback on Q&A responses",
    },
    {
        "keywords": ["clean", "reset", "benchmark"],
        "answer": "The application supports resetting all data to a clean state. This clears documents, chunks, Q&A history, and feedback data. It is useful for testing and benchmarking the full pipeline from scratch.",
        "excerpt": "The application supports resetting all data to a clean state",
    },
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class QaService:
    def __init__(
        self,
        persistence: PersistenceService,
        indexing_service: Optional[IndexingService] = None,
    ) -> None:
        self.persistence = persistence
        self.indexing_service = indexing_service or IndexingService(persistence)
        self.log = logger.for_service(SERVICE)
        self.log.info("QaService initialized")

    def ask(self, question: str) -> QAResponse:
        """Ask a question and get a grounded answer with citations."""
        start_time = time.monotonic()
        self.log.info("Processing question", {"question": question, "questionLength": len(question)})

        # Simulate processing delay
        time.sleep(0.1 + random.random() * 0.4)

        chunks = self.indexing_service.get_all_chunks()
        citations: List[Citation] = []

        if len(chunks) > 0:
            question_words = [w for w in _WHITESPACE_RE.split(question.lower()) if len(w) > 2]
            self.log.debug("Tokenized question", {"words": question_words, "chunkPool": len(chunks)})

            scored = []
            for chunk in chunks:
                content_lower = chunk["content"].lower()
                score = sum(1 for word in question_words if word in content_lower)
                scored.append({"chunk": chunk, "score": score})

            relevant = sorted(
                [s for s in scored if s["score"] > 0],
                key=lambda s: s["score"],
                reverse=True,
            )[:2]

            docs = self.persistence.read_json("documents-meta.json") or []

            for item in relevant:
                chunk = item["chunk"]
                doc = next((d for d in docs if d["id"] == chunk["documentId"]), None)
                citations.append(
                    {
                        "documentId": chunk["documentId"],
                        "documentTitle": doc["title"] if doc else "Unknown Document",
                        "chunkIndex": chunk["index"],
                        "excerpt": chunk["content"][:200],
                    }
                )
                self.log.debug(
                    "Citation matched",
                    {"documentId": chunk["documentId"], "chunkIndex": chunk["index"], "score": item["score"]},
                )
        else:
            self.log.warn("No chunks available for retrieval -- index documents first")

        answer = self._generate_answer(question, citations)

        response: QAResponse = {
            "answer": answer,
            "citations": citations,
            "confidence": 0.85 if len(citations) > 0 else 0.3,
            "timestamp": _now_iso(),
        }

        self._save_to_history(question, response)

        duration_ms = int((time.monotonic() - start_time) * 1000)
        self.log.info(
            "Answer generated",
            {
                "confidence": response["confidence"],
                "citationCount": len(citations),
                "answerLength": len(answer),
                "durationMs": duration_ms,
            },
        )
        return response

    def get_history(self) -> List[QAHistory]:
        """Get the Q&A history."""
        history = self.persistence.read_json(QA_HISTORY_FILE) or []
        self.log.debug("Retrieved Q&A history", {"count": len(history)})
        return history

    def clear_history(self) -> None:
        """Clear the Q&A history."""
        self.persistence.write_json(QA_HISTORY_FILE, [])
        self.log.info("Q&A history cleared")

    def submit_feedback(
        self,
        qa_timestamp: str,
        question: str,
        rating: FeedbackRating,
        comment: str = "",
    ) -> FeedbackEntry:
        """Submit feedback for a Q&A response."""
        entry: FeedbackEntry = {
            "id": str(uuid.uuid4()),
            "qaTimestamp": qa_timestamp,
            "question": question,
            "rating": rating,
            "comment": comment,
            "submittedAt": _now_iso(),
        }

        feedback = self.get_feedback()
        feedback.append(entry)
        self.persistence.write_json(FEEDBACK_FILE, feedback)

        self.log.info(
            "Feedback submitted",
            {"feedbackId": entry["id"], "rating": entry["rating"], "questionLength": len(question)},
        )
        return entry

    def get_feedback(self) -> List[FeedbackEntry]:
        """Get all feedback entries."""
        return self.persistence.read_json(FEEDBACK_FILE) or []

    def _generate_answer(self, question: str, citations: List[Citation]) -> str:
        question_lower = question.lower()
        for pattern in MOCK_PATTERNS:
            if any(kw in question_lower for kw in pattern["keywords"]):
                if len(citations) > 0:
                    return (
                        f'{pattern["answer"]} Based on the document '
                        f'"{citations[0]["documentTitle"]}", '
                        f'{citations[0]["excerpt"][:100]}.'
                    )
                return pattern["answer"]

        if len(citations) > 0:
            return (
                "Based on the available documents, the most relevant information comes "
                f'from "{citations[0]["documentTitle"]}": {citations[0]["excerpt"][:150]}. '
                "However, a more specific answer would require additional context."
            )

        return (
            "No relevant documents have been indexed yet. Please import and index "
            "documents before asking questions."
        )

    def _save_to_history(self, question: str, response: QAResponse) -> None:
        history = self.get_history()
        history.append({"question": question, "response": response})
        self.persistence.write_json(QA_HISTORY_FILE, history)
