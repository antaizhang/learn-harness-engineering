"""cleanup_scanner.py

扫描一个项目目录，找出遗留产物、死代码、结构性违规，并输出一份清理报告。
用来落实「每个会话结束时都留下干净状态」这条原则。

用法：
  python3 docs/zh/lectures/lecture-12.../code/cleanup_scanner.py [path]
  （不传路径时默认当前工作目录）

运行：python3 docs/zh/lectures/lecture-12-why-every-session-must-leave-a-clean-state/code/cleanup_scanner.py
"""

import os
import sys
from dataclasses import dataclass, field
from typing import Callable


# ---------------------------------------------------------------------------
# 类型
# ---------------------------------------------------------------------------

@dataclass
class ScannerCheck:
    category: str
    name: str
    severity: str  # "critical" | "warning" | "info"
    description: str
    scan: Callable[[str], list[str]]


@dataclass
class ScanResult:
    category: str
    check: str
    severity: str
    found: list[str]
    description: str


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", "coverage", "__pycache__", ".venv", "venv"}


def find_files(base: str, extensions: list[str]) -> list[str]:
    found: list[str] = []

    def walk(current: str, depth: int) -> None:
        if depth > 4:  # 限制递归深度
            return
        try:
            entries = list(os.scandir(current))
        except OSError:
            return  # 跳过读不了的目录
        for entry in entries:
            if entry.is_dir():
                if entry.name in SKIP_DIRS:
                    continue
                walk(entry.path, depth + 1)
            elif entry.is_file():
                if any(entry.name.endswith(ext) for ext in extensions):
                    found.append(os.path.relpath(entry.path, base))

    walk(base, 0)
    return found


def scan_for_patterns(directory: str, patterns: list[str], results: list[str], base_dir: str) -> None:
    try:
        entries = list(os.scandir(directory))
    except OSError:
        return
    for entry in entries:
        if entry.is_dir():
            if entry.name not in SKIP_DIRS:
                scan_for_patterns(entry.path, patterns, results, base_dir)
            continue
        if not entry.name.endswith((".py", ".pyi")):
            continue
        try:
            with open(entry.path, encoding="utf-8") as f:
                lines = f.read().split("\n")
        except OSError:
            continue
        for i, line in enumerate(lines[:50]):
            for pattern in patterns:
                if pattern in line:
                    relative = os.path.relpath(entry.path, base_dir)
                    results.append(f"{relative}:{i + 1} contains {pattern}")


# ---------------------------------------------------------------------------
# 扫描器检查项
# ---------------------------------------------------------------------------

def create_checks() -> list[ScannerCheck]:
    def scan_temp(d: str) -> list[str]:
        return find_files(d, [".tmp", ".bak", ".swp", "~"])

    def scan_logs(d: str) -> list[str]:
        found: list[str] = []
        for p in find_files(d, [".log"]):
            norm = p.replace(os.sep, "/")
            if norm.startswith("src/") or norm.startswith("lib/") or norm.startswith("app/") \
                    or "/src/" in norm or "/lib/" in norm or "/app/" in norm:
                found.append(p)
        return found

    def scan_dead_code(d: str) -> list[str]:
        found: list[str] = []
        for src_dir in ("src", "lib", "app"):
            src_path = os.path.join(d, src_dir)
            if os.path.exists(src_path):
                scan_for_patterns(src_path, ["TODO:", "FIXME:", "HACK:", "XXX:"], found, d)
        return found

    def scan_gitignore(d: str) -> list[str]:
        return [] if os.path.exists(os.path.join(d, ".gitignore")) else [".gitignore (MISSING)"]

    def scan_build_artifacts(d: str) -> list[str]:
        found: list[str] = []
        for sub in ("src/dist", "src/build", "lib/dist", "lib/build"):
            if os.path.exists(os.path.join(d, *sub.split("/"))):
                found.append(sub + "/")
        return found

    def scan_nested_venv(d: str) -> list[str]:
        found: list[str] = []
        for src_dir in ("src", "lib", "app", "test", "tests"):
            for venv in (".venv", "venv"):
                if os.path.isdir(os.path.join(d, src_dir, venv)):
                    found.append(f"{src_dir}/{venv}/")
        return found

    def scan_session_indicators(d: str) -> list[str]:
        indicators = [
            "WIP.md", "IN_PROGRESS.md", "scratch.py", "scratch.js",
            "debug.py", "test_manual.py", "temp.py",
        ]
        return [f for f in indicators if os.path.exists(os.path.join(d, f))]

    def scan_empty_dirs(d: str) -> list[str]:
        found: list[str] = []
        for sub in ("src", "lib", "app", "test", "tests", "docs"):
            dp = os.path.join(d, sub)
            if os.path.isdir(dp):
                try:
                    if len(os.listdir(dp)) == 0:
                        found.append(sub + "/")
                except OSError:
                    pass
        return found

    def scan_env_files(d: str) -> list[str]:
        env_files = [".env", ".env.local", ".env.production", ".env.staging"]
        return [f for f in env_files if os.path.exists(os.path.join(d, f))]

    return [
        ScannerCheck("Stale Artifacts", "Temporary files (*.tmp, *.bak, *.swp)", "warning",
                     "Leftover temp files from editing or processing", scan_temp),
        ScannerCheck("Stale Artifacts", "Debug/log files in source", "warning",
                     "Log files that should not be in the source tree", scan_logs),
        ScannerCheck("Dead Code", "Unused code markers (placeholder detection)", "info",
                     "Files that may contain unused code (heuristic scan)", scan_dead_code),
        ScannerCheck("Structural Violations", "Missing .gitignore", "warning",
                     "No .gitignore file found -- risk of committing build artifacts", scan_gitignore),
        ScannerCheck("Structural Violations", "Build artifacts in source", "critical",
                     "Compiled output (dist/, build/) mixed with source", scan_build_artifacts),
        ScannerCheck("Structural Violations", "Virtualenv in source tree", "critical",
                     "virtualenv found outside root (nested dependency)", scan_nested_venv),
        ScannerCheck("Session Cleanliness", "Uncommitted changes indicator", "info",
                     "Checks for common artifacts of incomplete sessions", scan_session_indicators),
        ScannerCheck("Session Cleanliness", "Empty directories", "info",
                     "Empty directories that may be leftover from incomplete work", scan_empty_dirs),
        ScannerCheck("Configuration", "Environment files in source", "critical",
                     ".env files that may contain secrets", scan_env_files),
    ]


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------

def run() -> None:
    target_dir = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.getcwd()

    print("\n" + "=" * 90)
    print("  CLEANUP SCANNER -- Stale Artifact & Violation Report")
    print("=" * 90)
    print(f"  Scanning: {target_dir}\n")

    checks = create_checks()
    results: list[ScanResult] = []
    for check in checks:
        found = check.scan(target_dir)
        results.append(ScanResult(check.category, check.name, check.severity, found, check.description))

    header = f"| {'Category':<20}| {'Check':<40}| {'Severity':<10}| {'Count':<6}| Details"
    sep = f"|{'-' * 22}|{'-' * 42}|{'-' * 12}|{'-' * 8}|{'-' * 30}"
    print(header)
    print(sep)

    for r in results:
        count = len(r.found)
        detail = ", ".join(r.found[:2]) if count > 0 else "(clean)"
        if count > 0 and r.severity == "critical":
            marker = ">>"
        elif count > 0:
            marker = " *"
        else:
            marker = "  "
        print(f"{marker}| {r.category:<20}| {r.check:<40}| {r.severity:<10}| {str(count):<6}| {detail}")

    criticals = [r for r in results if r.severity == "critical" and r.found]
    warnings = [r for r in results if r.severity == "warning" and r.found]
    infos = [r for r in results if r.severity == "info" and r.found]
    clean = [r for r in results if not r.found]

    print("\n" + "=" * 90)
    print("  CLEANUP SUMMARY")
    print("=" * 90 + "\n")

    print(f"  Critical issues:    {len(criticals)}")
    print(f"  Warnings:           {len(warnings)}")
    print(f"  Info items:         {len(infos)}")
    print(f"  Clean checks:       {len(clean)}/{len(results)}")

    if criticals:
        print("\n  ACTION REQUIRED (Critical):")
        for c in criticals:
            print(f"    - {c.check}: {len(c.found)} item(s) found")
            print(f"      {c.description}")

    total_issues = sum(len(r.found) for r in results)
    if total_issues == 0:
        print("\n  Project is in a clean state. No issues found.\n")
    else:
        print(f"\n  Total issues found: {total_issues}. Run this scanner at the end of every session to maintain clean state.\n")


if __name__ == "__main__":
    run()
