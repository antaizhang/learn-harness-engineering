#!/usr/bin/env python3
"""check_architecture.py -- verify layer-boundary constraints.

Python/Flask equivalent of ``scripts/check-architecture.sh`` from the Electron
app. The layering is the same idea, translated to this codebase:

1. The service layer (``src/services``) must not depend on the web framework
   (no ``import flask``) -- business logic stays independent of the UI/transport.
2. The service layer must not import the web layer (``src.web``) -- services
   never reach back up into the IPC/HTTP layer.
3. Shared types (``src/shared``) must be a leaf: no imports of ``src.services``
   or ``src.web``.

Exit code 0 = all checks pass, 1 = violations found.
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _py_files(rel_dir: str) -> list[str]:
    base = os.path.join(ROOT, rel_dir)
    out: list[str] = []
    for dirpath, _dirs, files in os.walk(base):
        if "__pycache__" in dirpath:
            continue
        for name in files:
            if name.endswith(".py"):
                out.append(os.path.join(dirpath, name))
    return out


def _matches(path: str, pattern: re.Pattern[str]) -> bool:
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            if pattern.search(line):
                return True
    return False


def main() -> int:
    violations = 0
    print("=== Architecture Boundary Checks ===\n")

    flask_re = re.compile(r"^\s*(import\s+flask|from\s+flask\b)")
    web_re = re.compile(r"from\s+(\.\.web|src\.web)\b|import\s+src\.web\b")
    svc_re = re.compile(r"from\s+(\.\.services|\.services|src\.services)\b|import\s+src\.services\b")

    # Check 1: services must not import Flask
    print("Checking services for web-framework imports...")
    c1 = 0
    for f in _py_files("src/services"):
        if _matches(f, flask_re):
            print(f"  VIOLATION: {os.path.relpath(f, ROOT)} imports flask")
            c1 += 1
    violations += c1
    print("  PASS: No flask imports in services" if c1 == 0 else f"  {c1} violation(s)")
    print()

    # Check 2: services must not import the web layer
    print("Checking services for web-layer imports...")
    c2 = 0
    for f in _py_files("src/services"):
        if _matches(f, web_re):
            print(f"  VIOLATION: {os.path.relpath(f, ROOT)} imports the web layer")
            c2 += 1
    violations += c2
    print("  PASS: No web-layer imports in services" if c2 == 0 else f"  {c2} violation(s)")
    print()

    # Check 3: shared types must be a leaf
    print("Checking shared types for service/web imports...")
    c3 = 0
    for f in _py_files("src/shared"):
        if _matches(f, svc_re) or _matches(f, web_re):
            print(f"  VIOLATION: {os.path.relpath(f, ROOT)} imports services/web")
            c3 += 1
    violations += c3
    print("  PASS: shared/ is a leaf module" if c3 == 0 else f"  {c3} violation(s)")
    print()

    print("=== Summary ===")
    if violations > 0:
        print(f"FAIL: {violations} violation(s) found")
        return 1
    print("PASS: All architecture boundary checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
