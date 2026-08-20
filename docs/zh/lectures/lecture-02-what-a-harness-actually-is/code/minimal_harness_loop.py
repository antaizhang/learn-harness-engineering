"""minimal_harness_loop.py

一个最小 harness 循环的骨架：拼消息 -> 决定下一步动作 -> 调工具 -> 把结果追加回消息。
这是任何 agent harness 的核心结构，去掉了真实模型调用。

运行：python3 docs/zh/lectures/lecture-02-what-a-harness-actually-is/code/minimal_harness_loop.py
"""

from typing import Literal, TypedDict


class Message(TypedDict):
    role: Literal["user", "assistant"]
    content: str


class ToolResult(TypedDict):
    ok: bool
    output: str


def run_tool(name: str, tool_input: str) -> ToolResult:
    if name == "read_file":
        return {"ok": True, "output": f"contents of {tool_input}"}
    return {"ok": False, "output": f"unknown tool: {name}"}


def minimal_harness(messages: list[Message]) -> dict:
    next_action = {"tool": "read_file", "input": "README.md"}

    result = run_tool(next_action["tool"], next_action["input"])

    return {
        "messages": [
            *messages,
            {
                "role": "assistant",
                "content": f"Tool {next_action['tool']} returned: {result['output']}",
            },
        ]
    }


if __name__ == "__main__":
    state = minimal_harness([{"role": "user", "content": "Read the README"}])
    for msg in state["messages"]:
        print(f"[{msg['role']}] {msg['content']}")
