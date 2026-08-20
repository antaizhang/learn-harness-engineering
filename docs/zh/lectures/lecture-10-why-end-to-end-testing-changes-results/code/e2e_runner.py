"""e2e_runner.py

一个最小的端到端（E2E）测试 harness。把测试用例定义成一串用户动作序列
（导入文档 -> 索引 -> 提问 -> 校验引用）。模拟运行这些用例，
展示「单元测试全过」和「整条流水线真的能跑通」之间的差别。

运行：python3 docs/zh/lectures/lecture-10-why-end-to-end-testing-changes-results/code/e2e_runner.py
"""

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# 类型
# ---------------------------------------------------------------------------

@dataclass
class PipelineStep:
    name: str
    unit_test_passes: bool
    actual_behavior: str  # "works" | "fails" | "partial"
    failure_reason: Optional[str] = None


@dataclass
class TestCase:
    name: str
    steps: list[PipelineStep]


@dataclass
class TestResult:
    test_case: str
    unit_tests_passed: int
    unit_tests_total: int
    unit_test_result: str  # "PASS" | "FAIL"
    e2e_result: str        # "PASS" | "FAIL"
    e2e_failure_step: Optional[str] = None
    e2e_failure_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# 测试用例——单元测试全过、但 E2E 挂掉的真实场景
# ---------------------------------------------------------------------------

test_cases: list[TestCase] = [
    TestCase("Import document and ask question", [
        PipelineStep("Parse uploaded document", True, "works"),
        PipelineStep("Store document chunks", True, "works"),
        PipelineStep("Index chunks for retrieval", True, "partial",  # 索引了，但 embedding 维度不对
                     "Embedding dimension mismatch between indexer and retriever"),
        PipelineStep("Retrieve relevant chunks", True, "fails",  # 单测用的是维度正确的 mock 数据
                     "Empty results due to dimension mismatch from previous step"),
        PipelineStep("Generate answer with citations", True, "fails",  # 单测直接喂了已检索的 chunk
                     "No chunks retrieved, so answer has no citations"),
    ]),
    TestCase("Delete document and verify removal", [
        PipelineStep("Find document by ID", True, "works"),
        PipelineStep("Delete document record", True, "works"),
        PipelineStep("Remove indexed chunks", True, "fails",  # 索引里残留了孤儿 chunk
                     "Index cleanup query timed out, chunks remain orphaned"),
        PipelineStep("Verify document not in search results", True, "fails",  # 单测 mock 了搜索
                     "Orphaned chunks from previous step still appear in results"),
    ]),
    TestCase("Multi-user concurrent access", [
        PipelineStep("User A imports document", True, "works"),
        PipelineStep("User B imports document", True, "works"),
        PipelineStep("User A queries their document", True, "partial",  # 结果串了
                     "No user-scoping on retrieval, returns chunks from User B's doc"),
        PipelineStep("Verify only User A's results returned", True, "fails",
                     "Results include documents from other users"),
    ]),
]


# ---------------------------------------------------------------------------
# 跑测试
# ---------------------------------------------------------------------------

def run_unit_tests(tc: TestCase) -> tuple[int, int]:
    passed = sum(1 for s in tc.steps if s.unit_test_passes)
    return passed, len(tc.steps)


def run_e2e_test(tc: TestCase) -> tuple[bool, Optional[str], Optional[str]]:
    # 流水线：只要有一步真的失败，整条 E2E 就失败
    for step in tc.steps:
        if step.actual_behavior == "fails":
            return False, step.name, step.failure_reason or "Unknown failure"
    # 检查是否有 "partial" 的步骤（可能导致下游问题）
    partial_steps = [s for s in tc.steps if s.actual_behavior == "partial"]
    if partial_steps:
        # 在本模拟里，partial 步骤在下游总会导致失败
        last = partial_steps[-1]
        return False, last.name, last.failure_reason or "Partial completion"
    return True, None, None


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------

def run() -> None:
    print("\n" + "=" * 95)
    print("  E2E TEST RUNNER -- Unit Tests vs Full Pipeline")
    print("=" * 95)

    results: list[TestResult] = []
    for tc in test_cases:
        passed, total = run_unit_tests(tc)
        e2e_pass, fail_step, fail_reason = run_e2e_test(tc)
        results.append(TestResult(
            test_case=tc.name,
            unit_tests_passed=passed,
            unit_tests_total=total,
            unit_test_result="PASS" if passed == total else "FAIL",
            e2e_result="PASS" if e2e_pass else "FAIL",
            e2e_failure_step=fail_step,
            e2e_failure_reason=fail_reason,
        ))

    # 逐个测试用例的细节
    for tc, r in zip(test_cases, results):
        print("\n  Test Case: " + tc.name)
        print("  " + "-" * 70)

        header = f"  | {'Step':<40}| {'Unit Test':<11}| {'E2E Actual':<12}|"
        sep = f"  |{'-' * 42}|{'-' * 13}|{'-' * 14}|"
        print(header)
        print(sep)

        for step in tc.steps:
            ut_label = "PASS" if step.unit_test_passes else "FAIL"
            if step.actual_behavior == "works":
                e2e_label = "PASS"
            elif step.actual_behavior == "partial":
                e2e_label = "PARTIAL*"
            else:
                e2e_label = "FAIL"
            marker = ">>" if step.actual_behavior != "works" else "  "
            print(f"{marker}| {step.name:<40}| {ut_label:<11}| {e2e_label:<12}|")

        if r.e2e_failure_step:
            print(f"\n  E2E Failure at: {r.e2e_failure_step}")
            print(f"  Reason: {r.e2e_failure_reason}")

    print("\n" + "=" * 95)
    print("  COMPARISON: Unit Tests vs E2E Tests")
    print("=" * 95 + "\n")

    header = f"| {'Test Case':<35}| {'Unit Tests':<15}| {'E2E Result':<12}| Discrepancy"
    sep = f"|{'-' * 37}|{'-' * 17}|{'-' * 14}|{'-' * 30}"
    print(header)
    print(sep)

    for r in results:
        ut_label = f"{r.unit_tests_passed}/{r.unit_tests_total} {r.unit_test_result}"
        discrepancy = r.unit_test_result == "PASS" and r.e2e_result == "FAIL"
        disc_label = "UNIT PASS BUT E2E FAIL" if discrepancy else "Consistent"
        print(f"| {r.test_case:<35}| {ut_label:<15}| {r.e2e_result:<12}| {disc_label}")

    false_confidence = sum(1 for r in results if r.unit_test_result == "PASS" and r.e2e_result == "FAIL")
    print(f"\n  False confidence count: {false_confidence} of {len(results)}")
    print("  Unit tests pass but E2E reveals integration failures that units cannot catch.\n")


if __name__ == "__main__":
    run()
