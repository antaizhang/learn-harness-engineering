"""victory_detector.py

模拟一个宣称任务已完成的 agent，然后把它声称的状态和真实验证结果做对比。
输出「声称 vs 实际」，把 agent 说的和真实情况之间的差距高亮出来。

运行：python3 docs/zh/lectures/lecture-09-why-agents-declare-victory-too-early/code/victory_detector.py
"""

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# 类型
# ---------------------------------------------------------------------------

@dataclass
class VerificationCheck:
    description: str
    claimed: bool   # agent 说的
    actual: bool    # 真实情况
    severity: str   # "critical" | "warning"


@dataclass
class Task:
    name: str
    claimed_complete: bool
    checks: list[VerificationCheck]


# ---------------------------------------------------------------------------
# 模拟任务：声称状态 vs 真实状态
# ---------------------------------------------------------------------------

tasks: list[Task] = [
    Task("Add search endpoint", True, [
        VerificationCheck("Route handler exists", True, True, "critical"),
        VerificationCheck("Authentication middleware applied", True, False, "critical"),  # agent 忘了 auth
        VerificationCheck("Input validation added", True, True, "critical"),
        VerificationCheck("Unit tests written", True, False, "critical"),  # agent 跳过了测试
        VerificationCheck("Integration tests pass", True, False, "critical"),  # 没有测试可跑
        VerificationCheck("Documentation updated", True, False, "warning"),  # agent 跳过了文档
    ]),
    Task("Fix pagination bug", True, [
        VerificationCheck("Bug reproduction case confirmed", True, True, "critical"),
        VerificationCheck("Root cause identified", True, True, "critical"),
        VerificationCheck("Fix applied", True, True, "critical"),
        VerificationCheck("Edge cases tested", True, False, "warning"),  # 只测了正常路径
        VerificationCheck("Regression tests added", True, False, "critical"),
    ]),
    Task("Refactor auth module", True, [
        VerificationCheck("Old code removed", True, False, "warning"),  # 旧代码还在
        VerificationCheck("All existing tests still pass", True, False, "critical"),  # 两个测试挂了
        VerificationCheck("New auth flow works", True, True, "critical"),
        VerificationCheck("Migration guide written", True, False, "warning"),
    ]),
]


# ---------------------------------------------------------------------------
# 验证
# ---------------------------------------------------------------------------

@dataclass
class TaskVerification:
    task_name: str
    claimed_complete: bool
    actually_complete: bool
    total_checks: int
    claimed_passing: int
    actual_passing: int
    gaps: list[tuple[str, str]]  # (description, severity)


def verify_task(task: Task) -> TaskVerification:
    claimed_passing = sum(1 for c in task.checks if c.claimed)
    actual_passing = sum(1 for c in task.checks if c.actual)
    gaps = [(c.description, c.severity) for c in task.checks if c.claimed and not c.actual]
    return TaskVerification(
        task_name=task.name,
        claimed_complete=task.claimed_complete,
        actually_complete=len(gaps) == 0,
        total_checks=len(task.checks),
        claimed_passing=claimed_passing,
        actual_passing=actual_passing,
        gaps=gaps,
    )


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------

def run() -> None:
    print("\n" + "=" * 90)
    print("  VICTORY DETECTOR -- Claimed vs Actual Verification")
    print("=" * 90)

    verifications = [verify_task(t) for t in tasks]

    for v in verifications:
        print("\n  Task: " + v.task_name)
        print("  " + "-" * 70)
        print(f"  Agent claimed:  {'COMPLETE' if v.claimed_complete else 'NOT COMPLETE'}")
        print(f"  Actually is:    {'COMPLETE' if v.actually_complete else 'INCOMPLETE'}")

        if not v.actually_complete:
            print(f"  MISMATCH: Agent declared victory but {len(v.gaps)} check(s) failed!")

        task = next(t for t in tasks if t.name == v.task_name)
        print("\n  Check detail:")
        header = f"  | {'Check':<40}| {'Claimed':<9}| {'Actual':<9}| {'Gap?':<6}|"
        sep = f"  |{'-' * 42}|{'-' * 11}|{'-' * 11}|{'-' * 8}|"
        print(header)
        print(sep)

        for check in task.checks:
            claimed_label = "PASS" if check.claimed else "FAIL"
            actual_label = "PASS" if check.actual else "FAIL"
            gap_label = "GAP" if check.claimed and not check.actual else ""
            marker = ">>" if gap_label else "  "
            print(f"{marker}| {check.description:<40}| {claimed_label:<9}| {actual_label:<9}| {gap_label:<6}|")

    print("\n" + "=" * 90)
    print("  OVERALL SUMMARY")
    print("=" * 90 + "\n")

    header = f"| {'Task':<28}| {'Claimed':<10}| {'Actual':<10}| {'Gaps':<6}| {'Accuracy':<10}|"
    sep = f"|{'-' * 30}|{'-' * 12}|{'-' * 12}|{'-' * 8}|{'-' * 12}|"
    print(header)
    print(sep)

    for v in verifications:
        accuracy = round(v.actual_passing / v.total_checks * 100)
        c_label = "Done" if v.claimed_complete else "Pending"
        a_label = "Done" if v.actually_complete else "Incomplete"
        print(f"| {v.task_name:<28}| {c_label:<10}| {a_label:<10}| {str(len(v.gaps)):<6}| {f'{accuracy}%':<10}|")

    total_gaps = sum(len(v.gaps) for v in verifications)
    false_victories = sum(1 for v in verifications if v.claimed_complete and not v.actually_complete)

    print(f"\n  False victories: {false_victories} of {len(verifications)} tasks")
    print(f"  Total undetected gaps: {total_gaps}")
    print(f"\n  The agent declared 'done' on every task, but verification reveals {total_gaps} unmet criteria.")
    print("  Without explicit verification, premature victory declarations go unchecked.\n")


if __name__ == "__main__":
    run()
