"""failure_pattern_demo.py

模拟能力很强的 agent 也会掉进去的「四步失败模式」：
  1. 上下文不完整（Incomplete context）
  2. 局部看起来合理的改动（Locally reasonable changes）
  3. 没有全局验证（No global verification）
  4. 过早宣布完成（Premature completion）

运行：python3 docs/zh/lectures/lecture-01-why-capable-agents-still-fail/code/failure_pattern_demo.py
"""

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# 类型
# ---------------------------------------------------------------------------

@dataclass
class StepState:
    step: int
    name: str
    context_available: list[str]
    context_missing: list[str]
    action_taken: str
    local_outcome: str
    global_impact: str
    completed: bool


# ---------------------------------------------------------------------------
# 模拟的「模型」——一个简单的决策函数，只根据它拿到的上下文来输出。
# ---------------------------------------------------------------------------

def model_decide(context: list[str], task: str) -> str:
    def has(s: str) -> bool:
        return any(s in c for c in context)

    # 任务是「给 API 加一个搜索端点」。
    # 正确答案需要同时知道 auth 中间件和限流策略。
    if not has("auth"):
        return "Created new route handler /search without authentication checks"
    if not has("rate-limit"):
        return "Added search route with auth but forgot rate limiting"
    if not has("test-standards"):
        return "Implemented search with auth and rate-limit, but no tests"
    return "Fully implemented search endpoint with auth, rate-limit, and tests"


# ---------------------------------------------------------------------------
# 失败过程模拟
# ---------------------------------------------------------------------------

def simulate_failure_pattern() -> list[StepState]:
    steps: list[StepState] = []

    # ---- 第 1 步：上下文不完整 ----
    step1_context = ["project structure", "route definitions"]
    step1_missing = ["auth middleware", "rate-limiting policy", "test standards"]
    step1_decision = model_decide(step1_context, "add search endpoint")
    steps.append(StepState(
        step=1,
        name="Incomplete Context",
        context_available=step1_context,
        context_missing=step1_missing,
        action_taken=step1_decision,
        local_outcome="Looks good -- route compiles, returns data",
        global_impact="Missing auth means unauthenticated access to search",
        completed=False,
    ))

    # ---- 第 2 步：局部看起来合理的改动 ----
    # agent 收到提示后补上了 auth，但仍然缺其他上下文。
    step2_context = [*step1_context, "auth middleware"]
    step2_missing = ["rate-limiting policy", "test standards"]
    step2_decision = model_decide(step2_context, "add search endpoint")
    steps.append(StepState(
        step=2,
        name="Locally Reasonable Changes",
        context_available=step2_context,
        context_missing=step2_missing,
        action_taken=step2_decision,
        local_outcome="Route has auth -- looks complete locally",
        global_impact="No rate limiting means the endpoint can be abused",
        completed=False,
    ))

    # ---- 第 3 步：没有全局验证 ----
    step3_context = [*step2_context, "rate-limiting policy"]
    step3_missing = ["test standards"]
    step3_decision = model_decide(step3_context, "add search endpoint")
    steps.append(StepState(
        step=3,
        name="No Global Verification",
        context_available=step3_context,
        context_missing=step3_missing,
        action_taken=step3_decision,
        local_outcome="Feature appears fully implemented",
        global_impact="No tests -- regression risk, violates project standards",
        completed=False,
    ))

    # ---- 第 4 步：过早宣布完成 ----
    steps.append(StepState(
        step=4,
        name="Premature Completion",
        context_available=step3_context,
        context_missing=step3_missing,
        action_taken='Agent outputs: "Done. Added search endpoint."',
        local_outcome="Agent is satisfied, task marked complete",
        global_impact="Task is incomplete -- missing tests, no E2E verification",
        completed=True,
    ))

    return steps


# ---------------------------------------------------------------------------
# 对比表
# ---------------------------------------------------------------------------

def print_comparison_table(steps: list[StepState]) -> None:
    print("\n" + "=" * 90)
    print("  FAILURE PATTERN DEMO -- 4 Steps to a Broken Deliverable")
    print("=" * 90)

    for s in steps:
        print(f"\n  Step {s.step}: {s.name}")
        print("  " + "-" * 60)
        print(f"  Context available : {', '.join(s.context_available)}")
        print(f"  Context missing   : {', '.join(s.context_missing) or '(none)'}")
        print(f"  Action taken      : {s.action_taken}")
        print(f"  Local outcome     : {s.local_outcome}")
        print(f"  Global impact     : {s.global_impact}")
        print(f"  Marked complete?  : {'YES (premature)' if s.completed else 'No'}")

    # 汇总对比
    print("\n" + "=" * 90)
    print("  COMPARISON: What the agent saw vs. what was actually needed")
    print("=" * 90)

    total_required = [
        "project structure", "route definitions", "auth middleware",
        "rate-limiting policy", "test standards",
    ]
    final_available = steps[-1].context_available

    print("\n| Criterion              | Available | Missing | Status   |")
    print("|------------------------|-----------|---------|----------|")

    for item in total_required:
        avail = item in final_available
        row = (
            f"| {item:<23}| {('Yes' if avail else 'No'):<10}| "
            f"{('Yes' if not avail else ''):<8}| {('OK' if avail else 'GAP'):<9}|"
        )
        print(row)

    gap_count = sum(1 for i in total_required if i not in final_available)
    print(f"\n  Result: Agent completed with {gap_count} of {len(total_required)} context items missing.")
    print("  This is the core failure pattern: each step looked reasonable in isolation.\n")


# ---------------------------------------------------------------------------
# 运行
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print_comparison_table(simulate_failure_pattern())
