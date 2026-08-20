"""benchmark_runner.py

读取一份基准任务定义（一组带有通过标准的任务），「执行」每个任务，
记录耗时和通过/失败，输出一份对比报告，展示哪些任务通过、哪些失败。

运行：python3 docs/zh/lectures/lecture-12-why-every-session-must-leave-a-clean-state/code/benchmark_runner.py
"""

import math
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# 类型
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkTask:
    id: str
    name: str
    category: str
    pass_criteria: list[str]
    expected_duration_ms: int
    actual_duration_ms: int
    actual_pass: bool
    failure_reason: Optional[str] = None


@dataclass
class BenchmarkResult:
    id: str
    name: str
    category: str
    criteria_total: int
    criteria_passed: int
    passed: bool
    expected_ms: int
    actual_ms: int
    duration_delta: int
    failure_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# 基准任务定义
# ---------------------------------------------------------------------------

benchmark_tasks: list[BenchmarkTask] = [
    BenchmarkTask("bench-001", "Import markdown document", "Document Pipeline",
                  ["File accepted", "Chunks created", "Metadata stored"], 100, 95, True),
    BenchmarkTask("bench-002", "Import PDF document", "Document Pipeline",
                  ["File accepted", "Text extracted", "Chunks created", "Metadata stored"], 200, 310, False,
                  "PDF text extraction failed on page 3 -- encoding issue"),
    BenchmarkTask("bench-003", "Ask grounded question", "Q&A Pipeline",
                  ["Query received", "Relevant chunks retrieved", "Answer generated", "Citations present"], 500, 480, True),
    BenchmarkTask("bench-004", "Ask question with no relevant docs", "Q&A Pipeline",
                  ["Query received", "Graceful 'no results' message", "No hallucinated citations"], 400, 420, False,
                  "Model hallucinated a citation instead of saying 'no results'"),
    BenchmarkTask("bench-005", "Delete imported document", "Document Pipeline",
                  ["Document removed from list", "Chunks removed from index", "No orphan data"], 150, 145, True),
    BenchmarkTask("bench-006", "Concurrent user access", "Security",
                  ["Users isolated", "No cross-user data leak", "Performance within SLA"], 300, 850, False,
                  "Cross-user data leak detected + response time exceeded SLA (850ms > 500ms)"),
    BenchmarkTask("bench-007", "Session continuity after restart", "Reliability",
                  ["State persisted", "Session recovers", "No data loss"], 200, 180, True),
    BenchmarkTask("bench-008", "API rate limiting", "Security",
                  ["Rate limit enforced", "429 response after limit", "Legitimate traffic unaffected"], 100, 100, True),
]


# ---------------------------------------------------------------------------
# 执行模拟
# ---------------------------------------------------------------------------

def execute_benchmark(tasks: list[BenchmarkTask]) -> list[BenchmarkResult]:
    results: list[BenchmarkResult] = []
    for task in tasks:
        criteria_passed = (
            len(task.pass_criteria) if task.actual_pass
            else math.floor(len(task.pass_criteria) * 0.5)
        )
        results.append(BenchmarkResult(
            id=task.id,
            name=task.name,
            category=task.category,
            criteria_total=len(task.pass_criteria),
            criteria_passed=criteria_passed,
            passed=task.actual_pass,
            expected_ms=task.expected_duration_ms,
            actual_ms=task.actual_duration_ms,
            duration_delta=task.actual_duration_ms - task.expected_duration_ms,
            failure_reason=task.failure_reason,
        ))
    return results


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------

def run() -> None:
    print("\n" + "=" * 100)
    print("  BENCHMARK RUNNER -- Task Execution Report")
    print("=" * 100)

    results = execute_benchmark(benchmark_tasks)

    header = (f"| {'ID':<10}| {'Task':<35}| {'Category':<18}| {'Pass?':<6}| "
              f"{'Criteria':<10}| {'Expected':<10}| {'Actual':<10}| {'Delta':<8}|")
    sep = (f"|{'-' * 12}|{'-' * 37}|{'-' * 20}|{'-' * 8}|"
           f"{'-' * 12}|{'-' * 12}|{'-' * 12}|{'-' * 10}|")
    print("\n" + header)
    print(sep)

    for r in results:
        pass_label = "PASS" if r.passed else "FAIL"
        criteria_label = f"{r.criteria_passed}/{r.criteria_total}"
        delta_label = f"+{r.duration_delta}ms" if r.duration_delta >= 0 else f"{r.duration_delta}ms"
        marker = "  " if r.passed else ">>"
        print(f"{marker}| {r.id:<10}| {r.name:<35}| {r.category:<18}| {pass_label:<6}| "
              f"{criteria_label:<10}| {f'{r.expected_ms}ms':<10}| {f'{r.actual_ms}ms':<10}| {delta_label:<8}|")

    failures = [r for r in results if not r.passed]
    if failures:
        print("\n" + "-" * 100)
        print("  FAILURE DETAILS")
        print("-" * 100)
        for f in failures:
            sign = "+" if f.duration_delta >= 0 else ""
            print(f"\n  [{f.id}] {f.name}")
            print(f"    Category:    {f.category}")
            print(f"    Criteria:    {f.criteria_passed}/{f.criteria_total} passed")
            print(f"    Reason:      {f.failure_reason or 'Unknown'}")
            print(f"    Timing:      Expected {f.expected_ms}ms, actual {f.actual_ms}ms (delta: {sign}{f.duration_delta}ms)")

    print("\n" + "=" * 100)
    print("  SUMMARY BY CATEGORY")
    print("=" * 100 + "\n")

    categories = list(dict.fromkeys(r.category for r in results))
    print(f"| {'Category':<20}| {'Total':<8}| {'Passed':<8}| {'Failed':<8}| {'Pass Rate':<12}|")
    print(f"|{'-' * 22}|{'-' * 10}|{'-' * 10}|{'-' * 10}|{'-' * 14}|")

    for cat in categories:
        cat_results = [r for r in results if r.category == cat]
        cat_passed = sum(1 for r in cat_results if r.passed)
        cat_failed = len(cat_results) - cat_passed
        rate = round(cat_passed / len(cat_results) * 100)
        print(f"| {cat:<20}| {str(len(cat_results)):<8}| {str(cat_passed):<8}| {str(cat_failed):<8}| {f'{rate}%':<12}|")

    total_passed = sum(1 for r in results if r.passed)
    total_failed = len(results) - total_passed
    print("\n" + "-" * 100)
    print(f"  OVERALL: {total_passed}/{len(results)} passed ({round(total_passed / len(results) * 100)}%), {total_failed} failures")
    print("=" * 100 + "\n")


if __name__ == "__main__":
    run()
