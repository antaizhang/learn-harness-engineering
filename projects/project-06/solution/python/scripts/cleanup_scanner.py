#!/usr/bin/env python3
"""cleanup_scanner.py -- check the data directory for stale/inconsistent artifacts.

Python equivalent of ``scripts/cleanup-scanner.sh``. Examines the application's
data directory for:

* Orphaned content files (content without metadata)
* Dangling chunk files (chunks without index entries)
* Missing content files (metadata without content)
* Inconsistent metadata (indexed docs without chunks)
* Stale Q&A references (history referencing deleted docs)

Usage: python scripts/cleanup_scanner.py [data-dir]

If ``data-dir`` is not given it defaults to the app's data directory
(``.kb-data/knowledge-base-data`` under the project, or ``KB_DATA_DIR``).
"""

from __future__ import annotations

import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _default_data_dir() -> str:
    env = os.environ.get("KB_DATA_DIR")
    if env:
        return env
    return os.path.join(_ROOT, ".kb-data", "knowledge-base-data")


def _load_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def main(argv: list[str]) -> int:
    data_dir = argv[1] if len(argv) >= 2 else _default_data_dir()
    print("=== Cleanup Scanner ===")
    print(f"Data directory: {data_dir}\n")

    if not os.path.isdir(data_dir):
        print("[INFO] Data directory does not exist. Nothing to scan.")
        print("This is normal for a fresh installation.")
        return 0

    issues = 0
    docs = _load_json(os.path.join(data_dir, "documents-meta.json"), [])
    doc_ids = {d["id"] for d in docs}
    index_meta = _load_json(os.path.join(data_dir, "index-meta.json"), {})
    content_dir = os.path.join(data_dir, "content")
    chunks_dir = os.path.join(data_dir, "chunks")

    # Check 1: Orphaned content files (content without metadata).
    print("[Check 1] Orphaned content files")
    if os.path.isdir(content_dir):
        for name in os.listdir(content_dir):
            if name.endswith(".txt") and name[:-4] not in doc_ids:
                print(f"  ORPHANED: content/{name} (no matching document metadata)")
                issues += 1

    # Check 2: Dangling chunk files (chunks without index entries).
    print("[Check 2] Dangling chunk files")
    if os.path.isdir(chunks_dir):
        for name in os.listdir(chunks_dir):
            if name.endswith(".json") and name[:-5] not in index_meta:
                print(f"  DANGLING: chunks/{name} (not referenced by index-meta.json)")
                issues += 1

    # Check 3: Missing content files (metadata without content).
    print("[Check 3] Missing content files")
    for doc in docs:
        if not os.path.exists(os.path.join(content_dir, f"{doc['id']}.txt")):
            print(f"  MISSING: content for document {doc['id']} ({doc.get('filename')})")
            issues += 1

    # Check 4: Inconsistent metadata (indexed docs without chunks).
    print("[Check 4] Inconsistent metadata")
    for doc in docs:
        if doc.get("status") == "indexed" and doc["id"] not in index_meta:
            print(f"  INCONSISTENT: {doc['id']} marked indexed but has no chunk index")
            issues += 1

    # Check 5: Stale Q&A references (history citing deleted docs).
    print("[Check 5] Stale Q&A references")
    history = _load_json(os.path.join(data_dir, "qa-history.json"), [])
    for item in history:
        for citation in item.get("response", {}).get("citations", []):
            if citation.get("documentId") not in doc_ids:
                print(f"  STALE: history cites missing document {citation.get('documentId')}")
                issues += 1

    print("\n=== Summary ===")
    if issues > 0:
        print(f"Found {issues} issue(s)")
        return 1
    print("No issues found. Data directory is clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
