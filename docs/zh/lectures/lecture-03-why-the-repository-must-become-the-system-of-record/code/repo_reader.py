"""repo_reader.py

读取一个目录结构，按「可发现性」给它打分。
检查项：AGENTS.md、docs/、架构文档、功能追踪、交接文件，
以及其他表明「仓库正在充当系统记录（system of record）」的信号。

用法：
  python3 docs/zh/lectures/lecture-03.../code/repo_reader.py [path]
  （不传路径时默认当前工作目录）

运行：python3 docs/zh/lectures/lecture-03-why-the-repository-must-become-the-system-of-record/code/repo_reader.py
"""

import os
import sys
from dataclasses import dataclass
from typing import Callable


# ---------------------------------------------------------------------------
# 打分标准
# ---------------------------------------------------------------------------

@dataclass
class CheckOutcome:
    points: int
    found: list[str]
    missing: list[str]


@dataclass
class Check:
    name: str
    description: str
    max_points: int
    check: Callable[[str], CheckOutcome]


def _any_exists(base: str, candidates: list[str]) -> list[str]:
    return [f for f in candidates if os.path.exists(os.path.join(base, f))]


def _any_dir(base: str, candidates: list[str]) -> list[str]:
    return [f for f in candidates if os.path.isdir(os.path.join(base, f))]


def _make_checks() -> list[Check]:
    def check_agents(d: str) -> CheckOutcome:
        candidates = ["AGENTS.md", "CLAUDE.md", ".claude/CLAUDE.md"]
        found = _any_exists(d, candidates)
        return CheckOutcome(15 if found else 0, found, [] if found else candidates)

    def check_docs(d: str) -> CheckOutcome:
        candidates = ["docs", "documentation", "doc"]
        found = _any_dir(d, candidates)
        return CheckOutcome(10 if found else 0, found, [] if found else ["docs/"])

    def check_arch(d: str) -> CheckOutcome:
        patterns = [
            "architecture.md", "ARCHITECTURE.md", "docs/architecture.md",
            "docs/architecture/", "design.md", "DESIGN.md",
        ]
        found = _any_exists(d, patterns)
        return CheckOutcome(15 if found else 0, found, [] if found else ["architecture.md or docs/architecture/"])

    def check_features(d: str) -> CheckOutcome:
        patterns = [
            "feature_list.json", "features.md", "FEATURES.md",
            "docs/features.md", "tasks.json", "TODO.md",
        ]
        found = _any_exists(d, patterns)
        return CheckOutcome(15 if found else 0, found, [] if found else ["feature_list.json or features.md"])

    def check_handoff(d: str) -> CheckOutcome:
        patterns = [
            "HANDOFF.md", "handoff.md", "SESSION_NOTES.md",
            "docs/handoff.md", ".handoff", "PROGRESS.md",
        ]
        found = _any_exists(d, patterns)
        return CheckOutcome(15 if found else 0, found, [] if found else ["HANDOFF.md or PROGRESS.md"])

    def check_tests(d: str) -> CheckOutcome:
        patterns = ["test", "tests", "__tests__", "spec"]
        found = _any_dir(d, patterns)
        return CheckOutcome(10 if found else 0, found, [] if found else ["test/ or tests/"])

    def check_config(d: str) -> CheckOutcome:
        patterns = ["package.json", "tsconfig.json", "pyproject.toml", "Cargo.toml", "go.mod"]
        found = _any_exists(d, patterns)
        return CheckOutcome(10 if found else 0, found, [] if found else ["package.json or equivalent"])

    def check_readme(d: str) -> CheckOutcome:
        patterns = ["README.md", "README.rst", "README.txt", "README"]
        found = _any_exists(d, patterns)
        return CheckOutcome(10 if found else 0, found, [] if found else ["README.md"])

    return [
        Check("AGENTS.md / CLAUDE.md", "Agent-readable instruction file at repo root", 15, check_agents),
        Check("Documentation directory", "Dedicated docs/ or documentation/ directory", 10, check_docs),
        Check("Architecture documentation", "Files describing system architecture", 15, check_arch),
        Check("Feature tracking", "Feature list or task tracking file", 15, check_features),
        Check("Handoff / session continuity", "Files for multi-session continuity", 15, check_handoff),
        Check("Testing structure", "Test directory or test configuration", 10, check_tests),
        Check("Configuration files", "Project config (package.json, pyproject.toml, etc.)", 10, check_config),
        Check("README", "Root README file", 10, check_readme),
    ]


# ---------------------------------------------------------------------------
# 生成报告
# ---------------------------------------------------------------------------

def score_repo(target_dir: str) -> None:
    resolved = os.path.abspath(target_dir)

    if not os.path.exists(resolved):
        print(f"  Error: Directory not found: {resolved}", file=sys.stderr)
        sys.exit(1)

    print("\n" + "=" * 80)
    print("  REPOSITORY DISCOVERABILITY SCORE")
    print("=" * 80)
    print(f"  Target: {resolved}\n")

    header = f"| {'Criterion':<30}| {'Points':<8}| {'Status':<10}| Details"
    sep = f"|{'-' * 32}|{'-' * 10}|{'-' * 12}|{'-' * 30}"
    print(header)
    print(sep)

    total_score = 0
    max_score = 0

    for check in _make_checks():
        result = check.check(resolved)
        total_score += result.points
        max_score += check.max_points
        status = "PASS" if result.points > 0 else "FAIL"
        detail = ", ".join(result.found) if result.found else result.missing[0]
        print(f"| {check.name:<30}| {f'{result.points}/{check.max_points}':<8}| {status:<10}| {detail}")

    print("\n" + "-" * 80)
    pct = total_score / max_score
    print(f"  TOTAL SCORE: {total_score} / {max_score}  ({round(pct * 100)}%)")

    if pct >= 0.9:
        grade = "A -- Repository is a strong system of record"
    elif pct >= 0.7:
        grade = "B -- Good foundation, minor gaps"
    elif pct >= 0.5:
        grade = "C -- Partial structure, significant gaps"
    elif pct >= 0.3:
        grade = "D -- Minimal structure, hard for agents to navigate"
    else:
        grade = "F -- Repository lacks discoverability signals"

    print(f"  GRADE: {grade}")
    print("=" * 80 + "\n")


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    score_repo(target)
