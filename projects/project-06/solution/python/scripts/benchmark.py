#!/usr/bin/env python3
"""benchmark.py -- performance benchmark suite for the Knowledge Base app.

Python equivalent of ``scripts/benchmark.sh``. Measures import throughput,
indexing speed, query latency, and data integrity by driving the real services
layer against a throwaway data directory seeded with the bundled sample docs.

Usage: python scripts/benchmark.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import time

# Make ``src`` importable when run from anywhere.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

# Keep benchmark output clean -- silence structured logs below errors.
os.environ.setdefault("LOG_LEVEL", "ERROR")

from src.services.document_service import DocumentService  # noqa: E402
from src.services.indexing_service import IndexingService  # noqa: E402
from src.services.persistence_service import PersistenceService  # noqa: E402
from src.services.qa_service import QaService  # noqa: E402

SAMPLE_DIR = os.path.join(_ROOT, "data", "sample-documents")


def main() -> int:
    bench_dir = tempfile.mkdtemp(prefix="kb-bench-")
    print("=== Knowledge Base Benchmark Suite ===\n")
    print(f"Working directory: {bench_dir}")
    print(f"Sample data: {SAMPLE_DIR}\n")

    persistence = PersistenceService(bench_dir)
    documents = DocumentService(persistence)
    indexing = IndexingService(persistence)
    qa = QaService(persistence, indexing)

    passed = 0
    total = 4

    # ---- Task 1: Import ----
    print("[1/4] Import Benchmark")
    start = time.monotonic()
    import_count = 0
    for name in sorted(os.listdir(SAMPLE_DIR)):
        path = os.path.join(SAMPLE_DIR, name)
        if os.path.isfile(path):
            doc = documents.import_document(path)
            print(f"  Imported: {doc['filename']} ({doc['size']} bytes)")
            import_count += 1
    import_ms = (time.monotonic() - start) * 1000
    if import_count >= 3:
        print(f"  PASS: {import_count} files imported in {import_ms:.0f}ms")
        passed += 1
    else:
        print(f"  FAIL: only {import_count} files imported (expected >= 3)")
    print()

    # ---- Task 2: Indexing ----
    print("[2/4] Indexing Benchmark")
    start = time.monotonic()
    status = indexing.start_indexing()
    index_ms = (time.monotonic() - start) * 1000
    total_chunks = len(indexing.get_all_chunks())
    if status["status"] == "ready" and total_chunks > 0:
        print(f"  PASS: {total_chunks} chunks indexed in {index_ms:.0f}ms")
        passed += 1
    else:
        print(f"  FAIL: indexing status={status['status']} chunks={total_chunks}")
    print()

    # ---- Task 3: Query latency ----
    print("[3/4] Query Benchmark")
    questions = [
        "What design and architecture patterns are used?",
        "How does the indexing pipeline chunk documents?",
        "How does retrieval rank chunks?",
    ]
    latencies = []
    grounded = 0
    for q in questions:
        start = time.monotonic()
        resp = qa.ask(q)
        latencies.append((time.monotonic() - start) * 1000)
        if resp["citations"]:
            grounded += 1
    avg = sum(latencies) / len(latencies)
    if grounded >= 1:
        print(f"  PASS: {grounded}/{len(questions)} grounded answers, avg latency {avg:.0f}ms")
        passed += 1
    else:
        print(f"  FAIL: no grounded answers (avg latency {avg:.0f}ms)")
    print()

    # ---- Task 4: Data integrity ----
    print("[4/4] Integrity Benchmark")
    docs = documents.list_documents()
    indexed = [d for d in docs if d.get("status") == "indexed"]
    ok = len(indexed) == import_count and all(d.get("chunks", 0) > 0 for d in indexed)
    if ok:
        print(f"  PASS: all {len(indexed)} documents indexed with chunk counts recorded")
        passed += 1
    else:
        print(f"  FAIL: {len(indexed)}/{import_count} documents show indexed status")
    print()

    print("=== Summary ===")
    print(f"Passed {passed}/{total} benchmark tasks")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
