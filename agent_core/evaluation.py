"""无需模型额度的 Agent 路由与安全边界离线评测。"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from agent_core.rag import MarkdownKnowledgeRetriever
from agent_core.models import AgentIntent
from agent_core.routing import classify_intent

DEFAULT_DATASET = Path(__file__).with_name("eval") / "agent_cases.jsonl"
DEFAULT_RAG_DATASET = Path(__file__).with_name("eval") / "rag_cases.jsonl"
DEFAULT_KNOWLEDGE_DIR = Path(__file__).resolve().parents[1] / "ai-ecommerce-assistant" / "knowledge_base"


@dataclass(frozen=True)
class EvaluationCase:
    id: str
    category: str
    query: str
    expected_intent: AgentIntent


@dataclass(frozen=True)
class RAGEvaluationCase:
    id: str
    query: str
    expected_source: str


def load_cases(path: Path = DEFAULT_DATASET) -> list[EvaluationCase]:
    cases: list[EvaluationCase] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            cases.append(EvaluationCase(**json.loads(line)))
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"评测集第 {line_number} 行格式错误: {exc}") from exc
    if not cases:
        raise ValueError("评测集不能为空")
    if len({case.id for case in cases}) != len(cases):
        raise ValueError("评测集 id 必须唯一")
    return cases


def evaluate_routing(cases: list[EvaluationCase]) -> dict[str, Any]:
    rows = []
    by_category: Counter[str] = Counter()
    correct_by_category: Counter[str] = Counter()
    expected_intents: Counter[AgentIntent] = Counter(case.expected_intent for case in cases)
    for case in cases:
        actual = classify_intent(case.query)
        passed = actual == case.expected_intent
        by_category[case.category] += 1
        if passed:
            correct_by_category[case.category] += 1
        rows.append({**asdict(case), "actual_intent": actual, "passed": passed})

    passed_count = sum(row["passed"] for row in rows)
    category_scores = {
        category: round(correct_by_category[category] / total * 100, 2)
        for category, total in sorted(by_category.items())
    }
    majority_intent, majority_count = expected_intents.most_common(1)[0]
    majority_accuracy = round(majority_count / len(rows) * 100, 2)
    accuracy = round(passed_count / len(rows) * 100, 2)
    return {
        "total": len(rows),
        "passed": passed_count,
        "accuracy_pct": accuracy,
        "majority_baseline": {
            "intent": majority_intent,
            "accuracy_pct": majority_accuracy,
        },
        "lift_over_majority_pct_points": round(accuracy - majority_accuracy, 2),
        "category_accuracy_pct": category_scores,
        "failures": [row for row in rows if not row["passed"]],
    }


def load_rag_cases(path: Path = DEFAULT_RAG_DATASET) -> list[RAGEvaluationCase]:
    return [
        RAGEvaluationCase(**json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


async def evaluate_retrieval(
    cases: list[RAGEvaluationCase],
    knowledge_dir: Path = DEFAULT_KNOWLEDGE_DIR,
) -> dict[str, Any]:
    retriever = MarkdownKnowledgeRetriever(knowledge_dir)
    reciprocal_ranks: list[float] = []
    failures: list[dict[str, Any]] = []
    for case in cases:
        sources = await retriever.retrieve(case.query, top_k=3)
        filenames = [source.filename for source in sources]
        try:
            rank = filenames.index(case.expected_source) + 1
        except ValueError:
            rank = 0
            failures.append({**asdict(case), "actual_sources": filenames})
        reciprocal_ranks.append(1 / rank if rank else 0)
    hits = len(cases) - len(failures)
    return {
        "total": len(cases),
        "recall_at_3_pct": round(hits / len(cases) * 100, 2),
        "mrr": round(sum(reciprocal_ranks) / len(cases), 4),
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="运行 Agent 离线路由评测")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, help="可选 JSON 报告路径")
    args = parser.parse_args()

    report = evaluate_routing(load_cases(args.dataset))
    report["retrieval"] = asyncio.run(evaluate_retrieval(load_rag_cases()))
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    passed = report["accuracy_pct"] >= 90 and report["retrieval"]["recall_at_3_pct"] >= 80
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
