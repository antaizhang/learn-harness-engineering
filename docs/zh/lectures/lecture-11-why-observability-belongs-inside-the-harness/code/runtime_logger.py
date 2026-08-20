"""runtime_logger.py

一个结构化日志模块的演示。对比诊断故障时，随手 print 的输出
和结构化 JSON 日志输出的差别。内置一个「埋好的故障」场景，
展示结构化日志如何更快定位问题。

运行：python3 docs/zh/lectures/lecture-11-why-observability-belongs-inside-the-harness/code/runtime_logger.py
"""

import json
import random
import string
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


# ---------------------------------------------------------------------------
# 类型
# ---------------------------------------------------------------------------

@dataclass
class StructuredLogEntry:
    timestamp: str
    level: str  # "info" | "warn" | "error" | "debug"
    component: str
    action: str
    correlation_id: str
    duration_ms: Optional[int] = None
    input: Any = None
    output: Any = None
    error: Optional[str] = None


@dataclass
class PipelineStage:
    component: str
    action: str
    duration_ms: int
    success: bool
    error_message: Optional[str] = None
    input: Any = None
    output: Any = None


# ---------------------------------------------------------------------------
# 带有一个埋好故障的模拟流水线
# ---------------------------------------------------------------------------

CORRELATION_ID = "req-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))


def run_pipeline() -> list[PipelineStage]:
    return [
        PipelineStage("DocumentLoader", "parse_upload", 45, True,
                      input={"filename": "report.pdf", "size": "2.3MB"},
                      output={"chunks": 47}),
        PipelineStage("ChunkIndexer", "embed_and_store", 230, True,
                      input={"chunks": 47},
                      output={"indexed": 47, "embeddingDim": 1536}),
        PipelineStage("QueryRouter", "route_query", 12, True,
                      input={"query": "What is the revenue target?"},
                      output={"routedTo": "RetrievalEngine"}),
        # 埋好的故障：因维度不匹配，检索返回 0 条结果
        PipelineStage("RetrievalEngine", "semantic_search", 180, False,
                      error_message="Vector dimension mismatch: query embedding dim=768, index embedding dim=1536",
                      input={"query": "What is the revenue target?", "topK": 5},
                      output={"results": 0}),
        PipelineStage("AnswerGenerator", "generate_with_citations", 1500, True,  # 不崩，但答案很差
                      input={"context": [], "query": "What is the revenue target?"},
                      output={"answer": "I could not find relevant information.", "citations": 0}),
    ]


# ---------------------------------------------------------------------------
# 随手写日志（print 风格）
# ---------------------------------------------------------------------------

def print_ad_hoc_log(stages: list[PipelineStage]) -> None:
    print("Starting document Q&A pipeline...")
    print("User uploaded report.pdf")
    for stage in stages:
        if stage.success:
            print(f"{stage.component}: {stage.action} done ({stage.duration_ms}ms)")
        else:
            print(f"{stage.component}: something went wrong")
    print("Pipeline finished. Answer: I could not find relevant information.")


# ---------------------------------------------------------------------------
# 结构化日志（JSON）
# ---------------------------------------------------------------------------

def build_structured_log(stages: list[PipelineStage]) -> list[StructuredLogEntry]:
    entries: list[StructuredLogEntry] = []
    for stage in stages:
        entries.append(StructuredLogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level="info" if stage.success else "error",
            component=stage.component,
            action=stage.action,
            correlation_id=CORRELATION_ID,
            duration_ms=stage.duration_ms,
            input=stage.input,
            output=stage.output,
            error=stage.error_message,
        ))
    return entries


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------

def run() -> None:
    pipeline = run_pipeline()

    print("\n" + "=" * 90)
    print("  OBSERVABILITY DEMO -- Ad-hoc vs Structured Logging")
    print("=" * 90)

    # --- 随手输出 ---
    print("\n" + "-" * 90)
    print("  SCENARIO A: Ad-hoc print output")
    print("-" * 90 + "\n")
    print_ad_hoc_log(pipeline)
    print("\n  Diagnosis from ad-hoc logs: ??? Hard to tell what went wrong.")
    print("  The failure message is vague: 'something went wrong'.")
    print("  No dimensions, no input/output data, no correlation ID.")

    # --- 结构化输出 ---
    print("\n" + "-" * 90)
    print("  SCENARIO B: Structured JSON log output")
    print("-" * 90 + "\n")

    structured_entries = build_structured_log(pipeline)

    header = f"| {'Timestamp':<26}| {'Level':<6}| {'Component':<20}| {'Action':<25}| {'Duration':<9}| Error?"
    sep = f"|{'-' * 28}|{'-' * 8}|{'-' * 22}|{'-' * 27}|{'-' * 11}|{'-' * 30}"
    print(header)
    print(sep)

    for entry in structured_entries:
        has_error = (entry.error or "")[:30]
        marker = ">>" if entry.level == "error" else "  "
        print(f"{marker}| {entry.timestamp:<26}| {entry.level:<6}| {entry.component:<20}| {entry.action:<25}| {f'{entry.duration_ms}ms':<9}| {has_error}")

    # --- 诊断 ---
    print("\n" + "-" * 90)
    print("  AUTOMATED DIAGNOSIS FROM STRUCTURED LOGS")
    print("-" * 90 + "\n")

    errors = [e for e in structured_entries if e.level == "error"]
    for err in errors:
        print(f"  ROOT CAUSE: {err.component}.{err.action}")
        print(f"  Error: {err.error}")
        print(f"  Input: {json.dumps(err.input)}")
        print(f"  Output: {json.dumps(err.output)}")
        print(f"  Correlation ID: {err.correlation_id}")

    # 下游影响
    print("\n  DOWNSTREAM IMPACT:")
    answer_gen = next((e for e in structured_entries if e.component == "AnswerGenerator"), None)
    if answer_gen:
        out = answer_gen.output
        print(f"  AnswerGenerator received empty context ({json.dumps(answer_gen.input)})")
        print(f'  Produced answer: "{out["answer"]}" with {out["citations"]} citations')

    # 对比小结
    print("\n" + "=" * 90)
    print("  COMPARISON")
    print("=" * 90 + "\n")

    print(f"| {'Metric':<35}| {'Ad-hoc Logs':<18}| {'Structured Logs':<18}|")
    print(f"|{'-' * 37}|{'-' * 20}|{'-' * 20}|")
    print(f"| {'Root cause identifiable':<35}| {'No':<18}| {'Yes':<18}|")
    print(f"| {'Input/output traceable':<35}| {'No':<18}| {'Yes':<18}|")
    print(f"| {'Correlation across steps':<35}| {'No':<18}| {'Yes':<18}|")
    print(f"| {'Machine-parseable':<35}| {'No':<18}| {'Yes':<18}|")
    print(f"| {'Time to diagnose':<35}| {'Minutes (manual)':<18}| {'Seconds (auto)':<18}|")

    print("\n  Structured logging transforms debugging from guesswork into a deterministic lookup.\n")


if __name__ == "__main__":
    run()
