"""split_vs_monolithic.py

先构造一个单体指令文件（约 200 行），再演示把它拆成 4 个聚焦的小文件后，
任何一次查询所需读取的上下文会大幅下降。模拟一个「agent」查找某条具体规则，
并统计两种方式下它各自要读多少行。

运行：python3 docs/zh/lectures/lecture-04-why-one-giant-instruction-file-fails/code/split_vs_monolithic.py
"""

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# 模拟的单体指令文件（200 行规则）
# ---------------------------------------------------------------------------

@dataclass
class Line:
    line_number: int
    section: str
    content: str


monolithic_instructions: list[Line] = []

# 第 1 段：项目概览（1-50 行）
for i in range(1, 51):
    monolithic_instructions.append(Line(
        i, "Project Overview",
        "This project uses React 18 with TypeScript strict mode." if i == 25 else f"Overview detail line {i}",
    ))

# 第 2 段：代码风格规则（51-100 行）
for i in range(51, 101):
    if i == 72:
        content = "RULE: Always use explicit return types on exported functions."
    elif i == 78:
        content = "RULE: Use const assertions for immutable arrays."
    else:
        content = f"Style rule detail line {i}"
    monolithic_instructions.append(Line(i, "Code Style", content))

# 第 3 段：测试标准（101-150 行）
for i in range(101, 151):
    if i == 120:
        content = "RULE: Every new endpoint must have integration tests."
    elif i == 135:
        content = "RULE: Test files must mirror the source file structure."
    else:
        content = f"Testing detail line {i}"
    monolithic_instructions.append(Line(i, "Testing", content))

# 第 4 段：部署规则（151-200 行）
for i in range(151, 201):
    if i == 175:
        content = "RULE: Never deploy on Fridays. Deploy window is Tue-Thu 10am-3pm."
    else:
        content = f"Deployment detail line {i}"
    monolithic_instructions.append(Line(i, "Deployment", content))


# ---------------------------------------------------------------------------
# 拆分后的指令文件（4 个聚焦文件）
# ---------------------------------------------------------------------------

split_instructions: dict[str, list[Line]] = {
    "01-project-overview.md": [l for l in monolithic_instructions if l.section == "Project Overview"],
    "02-code-style.md": [l for l in monolithic_instructions if l.section == "Code Style"],
    "03-testing.md": [l for l in monolithic_instructions if l.section == "Testing"],
    "04-deployment.md": [l for l in monolithic_instructions if l.section == "Deployment"],
}


# ---------------------------------------------------------------------------
# 模拟查询——agent 需要找到某条具体规则
# ---------------------------------------------------------------------------

@dataclass
class Query:
    description: str
    target_rule: str
    relevant_section: str


queries: list[Query] = [
    Query("Find the rule about return types", "explicit return types", "Code Style"),
    Query("Find the deployment window rule", "deploy on Fridays", "Deployment"),
    Query("Find the integration test rule", "integration tests", "Testing"),
    Query("Find the test file structure rule", "mirror the source file", "Testing"),
]


# ---------------------------------------------------------------------------
# 搜索模拟
# ---------------------------------------------------------------------------

def search_monolithic(query: Query) -> tuple[int, bool]:
    # agent 必须从头逐行扫描，直到找到规则；最坏情况读完全部。
    lines_read = 0
    for line in monolithic_instructions:
        lines_read += 1
        if query.target_rule.lower() in line.content.lower():
            return lines_read, True
    return lines_read, False


def search_split(query: Query) -> tuple[int, bool, str]:
    # agent 根据段落知道该看哪个文件，只读那一个文件里的行。
    file_map = {
        "Project Overview": "01-project-overview.md",
        "Code Style": "02-code-style.md",
        "Testing": "03-testing.md",
        "Deployment": "04-deployment.md",
    }
    target_file = file_map[query.relevant_section]
    lines_read = 0
    for line in split_instructions[target_file]:
        lines_read += 1
        if query.target_rule.lower() in line.content.lower():
            return lines_read, True, target_file
    return lines_read, False, target_file


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------

def run() -> None:
    print("\n" + "=" * 90)
    print("  MONOLITHIC vs SPLIT INSTRUCTION FILES")
    print("=" * 90)

    total = len(monolithic_instructions)
    print(f"\n  Monolithic file: 1 file, {total} lines total")
    print(f"  Split files:     4 files, ~{round(total / 4)} lines each\n")

    header = f"| {'Query':<42}| {'Monolithic (lines)':<20}| {'Split (lines)':<15}| {'File Accessed':<22}| Savings"
    sep = f"|{'-' * 44}|{'-' * 22}|{'-' * 17}|{'-' * 24}|{'-' * 10}"
    print(header)
    print(sep)

    total_mono = 0
    total_split = 0

    for q in queries:
        mono_lines, _ = search_monolithic(q)
        split_lines, _, file_accessed = search_split(q)
        total_mono += mono_lines
        total_split += split_lines
        savings = round((mono_lines - split_lines) / mono_lines * 100)
        print(f"| {q.description:<42}| {str(mono_lines):<20}| {str(split_lines):<15}| {file_accessed:<22}| {savings}%")

    print(sep)
    avg_mono = round(total_mono / len(queries))
    avg_split = round(total_split / len(queries))
    avg_savings = round((avg_mono - avg_split) / avg_mono * 100)
    print(f"| {'AVERAGE':<42}| {str(avg_mono):<20}| {str(avg_split):<15}| {'(targeted file)':<22}| {avg_savings}%")

    print("\n" + "=" * 90)
    print("  KEY INSIGHT")
    print("=" * 90)
    print(f"  With a monolithic file, the agent must scan up to {total} lines for every query.")
    print(f"  With split files, it reads only the relevant {round(total / 4)}-line file.")
    print("  This means less context window usage, fewer hallucinations, and faster execution.\n")


if __name__ == "__main__":
    run()
