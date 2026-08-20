"""harness_vs_no_harness.py

把同一个任务执行器分别在「有 harness」和「没有 harness」两种情况下跑一遍，
并排对比。有 harness 的版本加上了显式规则、验证步骤和停止条件。

运行：python3 docs/zh/lectures/lecture-02-what-a-harness-actually-is/code/harness_vs_no_harness.py
"""

import time
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# 类型与辅助函数
# ---------------------------------------------------------------------------

@dataclass
class TaskResult:
    name: str
    passed: bool
    duration_ms: float
    issues: list[str] = field(default_factory=list)


@dataclass
class Task:
    name: str
    requires_auth: bool
    has_tests: bool
    within_scope: bool


tasks: list[Task] = [
    Task("Add search endpoint", requires_auth=True, has_tests=False, within_scope=True),
    Task("Add delete endpoint", requires_auth=True, has_tests=True, within_scope=True),
    Task("Refactor auth middleware", requires_auth=True, has_tests=True, within_scope=False),
    Task("Add health check", requires_auth=False, has_tests=True, within_scope=True),
    Task("Add rate limiter", requires_auth=True, has_tests=False, within_scope=True),
]


# ---------------------------------------------------------------------------
# 没有 harness——直接执行每个任务，不做任何检查
# ---------------------------------------------------------------------------

def run_without_harness(task_list: list[Task]) -> list[TaskResult]:
    results: list[TaskResult] = []

    for t in task_list:
        start = time.perf_counter()
        issues: list[str] = []

        # 「agent」干完活，然后就宣布完成。
        passed = True

        # 没有 harness 就发现不了的问题
        if t.requires_auth and not t.has_tests:
            issues.append("No tests for auth-protected endpoint")
            # agent 没注意到——照样标记为通过
        if not t.within_scope:
            issues.append("Task is outside current scope")
            # agent 没注意到

        duration = (time.perf_counter() - start) * 1000
        results.append(TaskResult(t.name, passed, duration, issues))

    return results


# ---------------------------------------------------------------------------
# 有 harness——规则、验证、停止条件
# ---------------------------------------------------------------------------

def run_with_harness(task_list: list[Task]) -> list[TaskResult]:
    rules = {"require_tests_for_auth": True, "enforce_scope": True}
    results: list[TaskResult] = []

    for t in task_list:
        start = time.perf_counter()
        issues: list[str] = []
        passed = True

        # 规则：带鉴权的端点必须有测试
        if rules["require_tests_for_auth"] and t.requires_auth and not t.has_tests:
            issues.append("BLOCKED: Auth-protected endpoint missing tests")
            passed = False

        # 规则：不越界
        if rules["enforce_scope"] and not t.within_scope:
            issues.append("BLOCKED: Task outside active scope -- skipped")
            passed = False

        # 验证：执行后再复查一遍
        if passed and not t.has_tests:
            issues.append("WARNING: No tests exist for this change")

        duration = (time.perf_counter() - start) * 1000
        results.append(TaskResult(t.name, passed, duration, issues))

    return results


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------

def true_pass_count(results: list[TaskResult]) -> int:
    """真正通过的任务数（有测试且在范围内，即没有任何 issue）。"""
    return sum(1 for r in results if r.passed and len(r.issues) == 0)


def print_comparison(no_harness: list[TaskResult], with_harness: list[TaskResult]) -> None:
    print("\n" + "=" * 80)
    print("  HARNESS vs NO-HARNESS COMPARISON")
    print("=" * 80)

    header = f"| {'Task':<28}| {'No-Harness':<12}| {'Issues(NH)':<35}| {'Harness':<12}| {'Issues(H)':<35}|"
    sep = f"|{'-' * 30}|{'-' * 14}|{'-' * 37}|{'-' * 14}|{'-' * 37}|"
    print("\n" + header)
    print(sep)

    for nh, wh in zip(no_harness, with_harness):
        nh_pass = "PASS" if nh.passed else "FAIL"
        wh_pass = "PASS" if wh.passed else "FAIL"
        nh_issue = nh.issues[0] if nh.issues else "(none)"
        wh_issue = wh.issues[0] if wh.issues else "(none)"
        print(f"| {nh.name:<28}| {nh_pass:<12}| {nh_issue:<35}| {wh_pass:<12}| {wh_issue:<35}|")

    # 指标
    nh_passed = sum(1 for r in no_harness if r.passed)
    wh_passed = sum(1 for r in with_harness if r.passed)
    nh_issues = sum(len(r.issues) for r in no_harness)
    wh_issues = sum(len(r.issues) for r in with_harness)

    print("\n" + "=" * 80)
    print("  SUMMARY METRICS")
    print("=" * 80)

    print(f"\n| {'Metric':<30}| {'No Harness':<15}| {'With Harness':<15}|")
    print(f"|{'-' * 32}|{'-' * 17}|{'-' * 17}|")
    print(f"| {'Tasks passed':<30}| {f'{nh_passed}/{len(no_harness)}':<15}| {f'{wh_passed}/{len(with_harness)}':<15}|")
    print(f"| {'Issues detected':<30}| {str(nh_issues):<15}| {str(wh_issues):<15}|")
    print(f"| {'False positives (passed but flawed)':<30}| {str(nh_passed - true_pass_count(no_harness)):<15}| {str(wh_passed - true_pass_count(with_harness)):<15}|")

    print("\n  The harness catches problems the no-harness run silently ignores.")
    print("  Without a harness, every task 'passes' even when it shouldn't.\n")


# ---------------------------------------------------------------------------
# 运行
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print_comparison(run_without_harness(tasks), run_with_harness(tasks))
