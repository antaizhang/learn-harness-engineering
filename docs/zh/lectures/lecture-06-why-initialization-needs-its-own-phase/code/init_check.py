"""init_check.py

用程序检查初始化的各项前置条件：
  - Python 版本
  - 依赖是否已安装（虚拟环境 / site-packages）
  - 源码目录是否存在
  - 配置文件是否齐全

再分别模拟「有显式初始化阶段」和「没有初始化阶段」两种情况，
展示缺失的前置条件如何在后续悄悄引发失败。

运行：python3 docs/zh/lectures/lecture-06-why-initialization-needs-its-own-phase/code/init_check.py
"""

import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable


# ---------------------------------------------------------------------------
# 类型
# ---------------------------------------------------------------------------

@dataclass
class CheckOutcome:
    passed: bool
    detail: str


@dataclass
class CheckItem:
    name: str
    category: str
    check: Callable[[], CheckOutcome]
    impact_if_missing: str


# ---------------------------------------------------------------------------
# 各项检查
# ---------------------------------------------------------------------------

def create_checks(target_dir: str) -> list[CheckItem]:
    def check_python_version() -> CheckOutcome:
        major, minor = sys.version_info[:2]
        return CheckOutcome(
            passed=(major, minor) >= (3, 9),
            detail=f"Detected: {sys.version.split()[0]} (need >= 3.9)",
        )

    def check_project_config() -> CheckOutcome:
        candidates = ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"]
        found = [f for f in candidates if os.path.exists(os.path.join(target_dir, f))]
        return CheckOutcome(
            passed=bool(found),
            detail=f"Found: {', '.join(found)}" if found else "No pyproject.toml / requirements.txt found",
        )

    def check_dependencies() -> CheckOutcome:
        candidates = [".venv", "venv", "env"]
        found = [d for d in candidates if os.path.isdir(os.path.join(target_dir, d))]
        return CheckOutcome(
            passed=bool(found),
            detail=f"Found virtualenv: {', '.join(found)}" if found else "No virtualenv (.venv/venv) found -- run python -m venv",
        )

    def check_pip() -> CheckOutcome:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "--version"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return CheckOutcome(True, f"Detected: {result.stdout.strip().split(' from ')[0]}")
            return CheckOutcome(False, "pip not available")
        except Exception:
            return CheckOutcome(False, "pip not available via python -m pip")

    def check_source_dir() -> CheckOutcome:
        candidates = ["src", "lib", "app"]
        found = [d for d in candidates if os.path.isdir(os.path.join(target_dir, d))]
        return CheckOutcome(
            passed=bool(found),
            detail=f"Found: {', '.join(found)}" if found else "No src/ lib/ or app/ directory found",
        )

    def check_test_dir() -> CheckOutcome:
        candidates = ["test", "tests", "__tests__", "spec"]
        found = [d for d in candidates if os.path.isdir(os.path.join(target_dir, d))]
        return CheckOutcome(
            passed=bool(found),
            detail=f"Found: {', '.join(found)}" if found else "No test directory found",
        )

    def check_git() -> CheckOutcome:
        exists = os.path.isdir(os.path.join(target_dir, ".git"))
        return CheckOutcome(exists, "Git repository detected" if exists else "No .git directory found")

    return [
        CheckItem("Python version >= 3.9", "Runtime", check_python_version,
                  "Modern syntax and stdlib features unavailable"),
        CheckItem("Project config exists", "Config", check_project_config,
                  "Cannot install dependencies or build the package"),
        CheckItem("Dependencies installed (virtualenv)", "Dependencies", check_dependencies,
                  "All imports fail at runtime"),
        CheckItem("pip available", "Toolchain", check_pip,
                  "Cannot install packages"),
        CheckItem("Source directory exists", "Structure", check_source_dir,
                  "Agent cannot locate source files to modify"),
        CheckItem("Test directory exists", "Structure", check_test_dir,
                  "Agent cannot find or run existing tests"),
        CheckItem("Git repository initialized", "Version Control", check_git,
                  "No rollback capability, no change history"),
    ]


# ---------------------------------------------------------------------------
# 模拟：有 / 没有初始化阶段
# ---------------------------------------------------------------------------

@dataclass
class SimResult:
    scenario: str
    failures_before_work: int
    work_attempted: bool
    work_succeeded: bool
    time_wasted_ms: int


def simulate_without_init() -> SimResult:
    # agent 跳过初始化，直接干活；每撞上一个缺失的前置条件才发现一次。
    checks = create_checks(os.getcwd())
    failures = 0
    time_wasted = 0
    for check in checks:
        if not check.check().passed:
            failures += 1
            time_wasted += 200  # 每发现一个缺口都要花时间
    return SimResult("NO INIT PHASE", 0, True, failures == 0, time_wasted)


def simulate_with_init() -> SimResult:
    # agent 先跑初始化阶段，一次性发现所有问题。
    checks = create_checks(os.getcwd())
    failures = sum(1 for check in checks if not check.check().passed)
    return SimResult("WITH INIT PHASE", failures, failures == 0, failures == 0, 0)


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------

def run() -> None:
    target_dir = os.getcwd()
    print("\n" + "=" * 80)
    print("  INITIALIZATION PREREQUISITE CHECK")
    print("=" * 80)
    print(f"  Target: {target_dir}\n")

    checks = create_checks(target_dir)
    results = [(c, c.check()) for c in checks]

    header = f"| {'Check':<35}| {'Category':<12}| {'Status':<6}| Detail"
    sep = f"|{'-' * 37}|{'-' * 14}|{'-' * 8}|{'-' * 40}"
    print(header)
    print(sep)

    for c, r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"| {c.name:<35}| {c.category:<12}| {status:<6}| {r.detail}")

    pass_count = sum(1 for _, r in results if r.passed)
    fail_count = len(results) - pass_count

    print("\n" + "-" * 80)
    print(f"  Results: {pass_count} passed, {fail_count} failed out of {len(results)} checks")

    if fail_count > 0:
        print("\n  FAILED CHECKS -- Impact if not resolved:")
        for c, r in results:
            if not r.passed:
                print(f"    - {c.name}: {c.impact_if_missing}")

    no_init = simulate_without_init()
    with_init = simulate_with_init()

    print("\n" + "=" * 80)
    print("  INIT PHASE COMPARISON")
    print("=" * 80 + "\n")

    print(f"| {'Metric':<35}| {'No Init Phase':<18}| {'With Init Phase':<18}|")
    print(f"|{'-' * 37}|{'-' * 20}|{'-' * 20}|")
    print(f"| {'Prerequisites checked upfront':<35}| {'No':<18}| {'Yes':<18}|")
    print(f"| {'Work attempted despite issues':<35}| {str(no_init.work_attempted):<18}| {str(with_init.work_attempted):<18}|")
    print(f"| {'Time wasted discovering issues late':<35}| {f'{no_init.time_wasted_ms}ms':<18}| {f'{with_init.time_wasted_ms}ms':<18}|")
    print(f"| {'Work succeeded':<35}| {str(no_init.work_succeeded):<18}| {str(with_init.work_succeeded):<18}|")

    print("\n  An explicit init phase catches problems before they waste time.\n")


if __name__ == "__main__":
    run()
