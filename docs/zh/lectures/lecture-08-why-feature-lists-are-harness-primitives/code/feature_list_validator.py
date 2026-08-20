"""feature_list_validator.py

读取 feature_list.json，校验它的 schema，并找出那些被标成 "passes": true
却没有验证证据（verification）的功能。输出一份结构化报告。
可以对任何带有 feature_list.json 的项目目录运行。

用法：
  python3 docs/zh/lectures/lecture-08.../code/feature_list_validator.py [path-to-dir]
  （不传路径时默认使用本脚本所在目录）

运行：python3 docs/zh/lectures/lecture-08-why-feature-lists-are-harness-primitives/code/feature_list_validator.py
"""

import json
import os
import sys
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# 类型
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    feature_id: str
    schema_valid: bool
    schema_errors: list[str]
    has_verification: bool
    marked_pass_without_evidence: bool
    passes: bool
    verification_count: int


# ---------------------------------------------------------------------------
# schema 校验
# ---------------------------------------------------------------------------

def validate_schema(entry: dict, index: int) -> list[str]:
    errors: list[str] = []
    label = entry.get("id") or f"entry {index + 1}"

    if not isinstance(entry.get("id"), str) or not entry.get("id"):
        errors.append(f"[{label}] Missing or invalid 'id' field")
    if not isinstance(entry.get("category"), str) or not entry.get("category"):
        errors.append(f"[{label}] Missing or invalid 'category' field")
    if not isinstance(entry.get("description"), str) or not entry.get("description"):
        errors.append(f"[{label}] Missing or invalid 'description' field")
    if "verification" in entry and not isinstance(entry["verification"], list):
        errors.append(f"[{label}] 'verification' must be an array if present")
    if "passes" in entry and not isinstance(entry["passes"], bool):
        errors.append(f"[{label}] 'passes' must be a boolean if present")

    return errors


# ---------------------------------------------------------------------------
# 证据校验
# ---------------------------------------------------------------------------

def check_evidence(entry: dict) -> tuple[bool, bool]:
    verification = entry.get("verification")
    has_verification = isinstance(verification, list) and len(verification) > 0
    marked_pass_without_evidence = entry.get("passes") is True and not has_verification
    return has_verification, marked_pass_without_evidence


# ---------------------------------------------------------------------------
# 处理功能列表
# ---------------------------------------------------------------------------

def process_feature_list(entries: list[dict]) -> list[ValidationResult]:
    results: list[ValidationResult] = []
    for index, entry in enumerate(entries):
        schema_errors = validate_schema(entry, index)
        has_verification, marked = check_evidence(entry)
        verification = entry.get("verification")
        results.append(ValidationResult(
            feature_id=entry.get("id") or f"entry-{index + 1}",
            schema_valid=len(schema_errors) == 0,
            schema_errors=schema_errors,
            has_verification=has_verification,
            marked_pass_without_evidence=marked,
            passes=entry.get("passes") is True,
            verification_count=len(verification) if isinstance(verification, list) else 0,
        ))
    return results


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------

def run() -> None:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    target_dir = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else script_dir
    file_path = os.path.join(target_dir, "feature_list.json")

    print("\n" + "=" * 90)
    print("  FEATURE LIST VALIDATOR")
    print("=" * 90)
    print(f"  Reading: {file_path}\n")

    if not os.path.exists(file_path):
        print(f"  ERROR: feature_list.json not found at {file_path}", file=sys.stderr)
        print("  Usage: python3 feature_list_validator.py [path-to-directory-containing-feature_list.json]\n", file=sys.stderr)
        sys.exit(1)

    try:
        with open(file_path, encoding="utf-8") as f:
            entries = json.load(f)
    except Exception as err:
        print(f"  ERROR: Could not parse feature_list.json: {err}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(entries, list):
        print("  ERROR: feature_list.json must contain a JSON array at the top level.", file=sys.stderr)
        sys.exit(1)

    # 为了演示，额外拼上一组测试用例
    demo_entries = [
        *entries,
        {
            "id": "qna-002",
            "category": "import",
            "description": "User can import a PDF document.",
            "verification": ["Upload a PDF file", "Verify it appears in the document list"],
            "passes": True,
        },
        {
            "id": "qna-003",
            "category": "grounded_qa",
            "description": "System hallucination rate is below 5%.",
            "verification": [],  # 空——没有证据
            "passes": True,       # 却被标成通过
        },
        {
            "id": "missing-fields",
            # 缺 'category' 和 'description'
            "passes": True,
        },
    ]

    results = process_feature_list(demo_entries)

    header = f"| {'Feature ID':<14}| {'Schema':<8}| {'Passes':<7}| {'Verifications':<14}| {'Evidence?':<12}| Notes"
    sep = f"|{'-' * 16}|{'-' * 10}|{'-' * 9}|{'-' * 16}|{'-' * 14}|{'-' * 30}"
    print(header)
    print(sep)

    for r in results:
        schema_label = "OK" if r.schema_valid else "INVALID"
        passes_label = "PASS" if r.passes else "FAIL"
        evidence_label = "Present" if r.has_verification else "MISSING"
        if r.marked_pass_without_evidence:
            notes = "FLAGGED: passes without evidence!"
        elif r.schema_errors:
            notes = r.schema_errors[0]
        else:
            notes = ""
        marker = ">>" if r.marked_pass_without_evidence else ("  " if r.schema_valid else "!!")
        print(f"{marker}| {r.feature_id:<14}| {schema_label:<8}| {passes_label:<7}| {str(r.verification_count):<14}| {evidence_label:<12}| {notes}")

    total = len(results)
    schema_ok = sum(1 for r in results if r.schema_valid)
    passing = sum(1 for r in results if r.passes)
    flagged = sum(1 for r in results if r.marked_pass_without_evidence)
    with_evidence = sum(1 for r in results if r.has_verification)

    print("\n" + "-" * 90)
    print("  SUMMARY")
    print("-" * 90)
    print(f"  Total features:                     {total}")
    print(f"  Schema valid:                       {schema_ok}/{total}")
    print(f"  Marked as passing:                  {passing}/{total}")
    print(f"  With verification evidence:         {with_evidence}/{total}")
    print(f"  Flagged (pass without evidence):    {flagged}")

    if flagged > 0:
        print(f'\n  WARNING: {flagged} feature(s) marked as "pass" without any verification evidence.')
        print("  These features need verification before they can be trusted.\n")
    else:
        print("\n  All passing features have verification evidence. Feature list is healthy.\n")


if __name__ == "__main__":
    run()
