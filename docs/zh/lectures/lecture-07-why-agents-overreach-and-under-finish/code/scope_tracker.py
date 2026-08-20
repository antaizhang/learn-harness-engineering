"""scope_tracker.py

读取一份功能列表和一份变更日志，强制执行「单一活跃功能」策略。
给定一串变更记录，标记出任何落在活跃功能范围之外的改动。
演示范围漂移（scope drift）是怎么发生的，以及追踪器如何把它抓出来。

运行：python3 docs/zh/lectures/lecture-07-why-agents-overreach-and-under-finish/code/scope_tracker.py
"""

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# 类型
# ---------------------------------------------------------------------------

@dataclass
class Feature:
    id: str
    name: str
    status: str  # "active" | "pending" | "done"


@dataclass
class ChangeLogEntry:
    step: int
    file: str
    description: str
    feature_id: str  # 这条改动声称所属的功能


# ---------------------------------------------------------------------------
# 示例数据
# ---------------------------------------------------------------------------

features: list[Feature] = [
    Feature("F-001", "Search endpoint", "active"),
    Feature("F-002", "Delete endpoint", "pending"),
    Feature("F-003", "Rate limiting", "pending"),
    Feature("F-004", "User dashboard", "pending"),
]

# 一份真实感的变更日志——agent 逐渐从活跃功能上漂移开去
change_log: list[ChangeLogEntry] = [
    ChangeLogEntry(1, "src/routes/search.py", "Add search route handler", "F-001"),
    ChangeLogEntry(2, "src/routes/search.py", "Add query parameter validation", "F-001"),
    ChangeLogEntry(3, "src/routes/search.py", "Add search results pagination", "F-001"),
    ChangeLogEntry(4, "src/routes/delete.py", "Add delete route handler", "F-002"),  # 漂移
    ChangeLogEntry(5, "src/middleware/rate_limit.py", "Add rate limiter middleware", "F-003"),  # 漂移
    ChangeLogEntry(6, "src/routes/search.py", "Integrate rate limiter into search", "F-001"),
    ChangeLogEntry(7, "src/dashboard/ui.py", "Create dashboard layout component", "F-004"),  # 漂移
    ChangeLogEntry(8, "src/routes/search.py", "Add search response formatting", "F-001"),
    ChangeLogEntry(9, "src/routes/delete.py", "Add delete confirmation logic", "F-002"),  # 漂移
    ChangeLogEntry(10, "src/routes/search.py", "Add search tests", "F-001"),
]


# ---------------------------------------------------------------------------
# 范围追踪器
# ---------------------------------------------------------------------------

@dataclass
class ScopeCheckResult:
    step: int
    file: str
    description: str
    feature_id: str
    in_scope: bool
    active_feature: str


def track_scope(feature_list: list[Feature], changes: list[ChangeLogEntry]) -> list[ScopeCheckResult]:
    active_features = [f for f in feature_list if f.status == "active"]
    active_ids = {f.id for f in active_features}
    active_names = ", ".join(f.name for f in active_features)

    return [
        ScopeCheckResult(
            step=c.step,
            file=c.file,
            description=c.description,
            feature_id=c.feature_id,
            in_scope=c.feature_id in active_ids,
            active_feature=active_names,
        )
        for c in changes
    ]


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------

def run() -> None:
    results = track_scope(features, change_log)

    print("\n" + "=" * 100)
    print("  SCOPE TRACKER -- Single Active Feature Enforcement")
    print("=" * 100)

    active = ", ".join(f"{f.id} ({f.name})" for f in features if f.status == "active")
    pending = ", ".join(f"{f.id} ({f.name})" for f in features if f.status == "pending")
    print(f"\n  Active feature: {active}")
    print(f"  Pending features: {pending}")

    print("\n" + "-" * 100)
    header = f"| {'Step':<5}| {'File':<35}| {'Description':<40}| {'Feature':<8}| {'In Scope':<10}|"
    sep = f"|{'-' * 7}|{'-' * 37}|{'-' * 42}|{'-' * 10}|{'-' * 12}|"
    print(header)
    print(sep)

    in_scope_count = 0
    drift_count = 0

    for r in results:
        scope_label = "OK" if r.in_scope else "DRIFT"
        if r.in_scope:
            in_scope_count += 1
        else:
            drift_count += 1
        marker = "  " if r.in_scope else ">>"
        print(f"{marker}| {str(r.step):<5}| {r.file:<35}| {r.description:<40}| {r.feature_id:<8}| {scope_label:<10}|")

    print("\n" + "=" * 100)
    print("  SCOPE DRIFT SUMMARY")
    print("=" * 100 + "\n")

    print(f"| {'Metric':<40}| {'Value':<15}|")
    print(f"|{'-' * 42}|{'-' * 17}|")
    print(f"| {'Total changes':<40}| {str(len(results)):<15}|")
    print(f"| {'Changes within active scope (F-001)':<40}| {str(in_scope_count):<15}|")
    print(f"| {'Changes outside active scope (DRIFT)':<40}| {str(drift_count):<15}|")
    print(f"| {'Features touched (total)':<40}| {str(len({r.feature_id for r in results})):<15}|")

    drift_features = list(dict.fromkeys(r.feature_id for r in results if not r.in_scope))
    if drift_features:
        print("\n  DRIFTED FEATURES:")
        for fid in drift_features:
            feat = next((f for f in features if f.id == fid), None)
            drift_changes = [r for r in results if r.feature_id == fid]
            print(f"    {fid} ({feat.name if feat else '?'}): {len(drift_changes)} unauthorized changes")

    print(f"\n  Without a scope tracker, the agent silently worked on {len(drift_features)} unrelated features.")
    print("  The tracker catches this drift and enforces the single-active-feature policy.\n")


if __name__ == "__main__":
    run()
