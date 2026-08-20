"""session_simulator.py

模拟两个会话协作完成一个多步任务：
  运行 1：没有交接文件——会话 B 从头开始，把会话 A 做过的活又做了一遍。
  运行 2：有交接文件——会话 B 从会话 A 停下的地方接着做。

运行：python3 docs/zh/lectures/lecture-05-why-long-running-tasks-lose-continuity/code/session_simulator.py
"""

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# 类型
# ---------------------------------------------------------------------------

@dataclass
class TaskStep:
    id: int
    name: str
    duration_ms: int


@dataclass
class SessionResult:
    session: str
    steps_completed: int
    total_duration_ms: int
    duplicated_steps: int
    output: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 任务定义
# ---------------------------------------------------------------------------

task_steps: list[TaskStep] = [
    TaskStep(1, "Read project structure", 50),
    TaskStep(2, "Understand existing auth module", 80),
    TaskStep(3, "Design new search endpoint", 60),
    TaskStep(4, "Implement search endpoint", 100),
    TaskStep(5, "Write integration tests", 70),
    TaskStep(6, "Update documentation", 40),
]


# ---------------------------------------------------------------------------
# 模拟会话执行器
# ---------------------------------------------------------------------------

def run_session(session_name: str, start_step: int, end_step: int) -> SessionResult:
    """模拟一个会话干活。"""
    output: list[str] = []
    total_duration = 0

    for i in range(start_step, end_step + 1):
        step = next(s for s in task_steps if s.id == i)
        total_duration += step.duration_ms
        output.append(f"  [{session_name}] Step {step.id}: {step.name} ({step.duration_ms}ms)")

    return SessionResult(session_name, end_step - start_step + 1, total_duration, 0, output)


# ---------------------------------------------------------------------------
# 运行 1：没有交接文件
# ---------------------------------------------------------------------------

def simulate_no_handoff() -> tuple[SessionResult, SessionResult]:
    # 会话 A 在超时前做完第 1-3 步
    session_a = run_session("Session A", 1, 3)
    # 会话 B 没有上下文，只能从头做
    session_b = run_session("Session B", 1, 6)
    session_b.duplicated_steps = 3  # 重做了 A 已经做过的第 1-3 步
    return session_a, session_b


# ---------------------------------------------------------------------------
# 运行 2：有交接文件
# ---------------------------------------------------------------------------

def simulate_with_handoff() -> tuple[SessionResult, SessionResult]:
    # 会话 A 做完第 1-3 步并写下交接文件
    session_a = run_session("Session A", 1, 3)
    # 会话 B 读了交接文件，从第 4 步开始
    session_b = run_session("Session B", 4, 6)
    session_b.duplicated_steps = 0
    return session_a, session_b


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------

def print_run(title: str, result: tuple[SessionResult, SessionResult]) -> None:
    session_a, session_b = result
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

    print("\n  Session A output:")
    for line in session_a.output:
        print(line)

    print("\n  Session B output:")
    for line in session_b.output:
        print(line)

    print("\n  Session B notes:")
    if session_b.duplicated_steps > 0:
        wasted = session_b.total_duration_ms - sum(t.duration_ms for t in task_steps[3:])
        print(f"    - Redid {session_b.duplicated_steps} steps that Session A already completed")
        print(f"    - Wasted {wasted}ms on duplicate work")
    else:
        print("    - Read handoff file, continued from step 4")
        print("    - No duplicate work performed")


def print_comparison() -> None:
    no_handoff = simulate_no_handoff()
    with_handoff = simulate_with_handoff()

    print_run("RUN 1: NO HANDOFF FILE", no_handoff)
    print_run("RUN 2: WITH HANDOFF FILE", with_handoff)

    print("\n" + "=" * 80)
    print("  COMPARISON TABLE")
    print("=" * 80 + "\n")

    header = f"| {'Metric':<35}| {'No Handoff':<15}| {'With Handoff':<15}|"
    sep = f"|{'-' * 37}|{'-' * 17}|{'-' * 17}|"
    print(header)
    print(sep)

    no_total = no_handoff[0].total_duration_ms + no_handoff[1].total_duration_ms
    with_total = with_handoff[0].total_duration_ms + with_handoff[1].total_duration_ms

    print(f"| {'Session A steps completed':<35}| {str(no_handoff[0].steps_completed):<15}| {str(with_handoff[0].steps_completed):<15}|")
    print(f"| {'Session B steps completed':<35}| {str(no_handoff[1].steps_completed):<15}| {str(with_handoff[1].steps_completed):<15}|")
    print(f"| {'Duplicated steps':<35}| {str(no_handoff[1].duplicated_steps):<15}| {str(with_handoff[1].duplicated_steps):<15}|")
    print(f"| {'Total work (ms)':<35}| {str(no_total):<15}| {str(with_total):<15}|")
    print(f"| {'Time saved by handoff':<35}| {'-':<15}| {f'{no_total - with_total}ms':<15}|")

    print("\n  A handoff file eliminates duplicate work and ensures continuity across sessions.\n")


if __name__ == "__main__":
    print_comparison()
