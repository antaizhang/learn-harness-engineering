"""Mock grounded Q&A with citations. Port of ``qa-service.ts``.

Answers are produced from keyword-matched mock patterns (no real LLM), exactly
like the original course app.
"""

from __future__ import annotations

import random
import re
import time
from datetime import datetime, timezone
from typing import List, Optional

from ..shared.types import Citation, QAHistory, QAResponse
from .indexing_service import IndexingService
from .logger import logger
from .persistence_service import PersistenceService

QA_HISTORY_FILE = "qa-history.json"

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
        self.log = logger.for_service("QaService")
        self.log.info("QaService initialized")

    def ask(self, question: str) -> QAResponse:
        """Ask a question and get a grounded answer with citations."""
        self.log.info("Processing question", {"question": question})

        # Simulate processing delay
        time.sleep(0.1 + random.random() * 0.4)

        chunks = self.indexing_service.get_all_chunks()
        citations: List[Citation] = []

        self.log.info("Retrieving from chunks", {"totalChunks": len(chunks)})

        if len(chunks) > 0:
            # Find relevant chunks using keyword matching
            question_words = [w for w in _WHITESPACE_RE.split(question.lower()) if len(w) > 2]
            scored = []
            for chunk in chunks:
                content_lower = chunk["content"].lower()
                score = sum(1 for word in question_words if word in content_lower)
                scored.append({"chunk": chunk, "score": score})

            # Take top 2 relevant chunks as citations
            relevant = sorted(
                [s for s in scored if s["score"] > 0],
                key=lambda s: s["score"],
                reverse=True,
            )[:2]

            self.log.info(
                "Keyword matching results",
                {"questionWords": len(question_words), "relevantChunks": len(relevant)},
            )

            # Get document metadata for citations
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

        # Generate answer from mock patterns or use fallback
        answer = self._generate_answer(question, citations)

        response: QAResponse = {
            "answer": answer,
            "citations": citations,
            "confidence": 0.85 if len(citations) > 0 else 0.3,
            "timestamp": _now_iso(),
        }

        self.log.info(
            "Q&A response generated",
            {
                "confidence": response["confidence"],
                "citationCount": len(citations),
                "answerLength": len(answer),
            },
        )

        # Save to history
        self._save_to_history(question, response)

        return response

    def get_history(self) -> List[QAHistory]:
        """Get the Q&A history."""
        return self.persistence.read_json(QA_HISTORY_FILE) or []

    def clear_history(self) -> None:
        """Clear the Q&A history."""
        self.persistence.write_json(QA_HISTORY_FILE, [])
        self.log.info("Q&A history cleared")

    def _generate_answer(self, question: str, citations: List[Citation]) -> str:
        # Match against mock patterns
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

        # Fallback answer
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
        self.log.info("Question saved to history", {"historyLength": len(history)})
