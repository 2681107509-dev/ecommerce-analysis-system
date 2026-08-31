"""无需模型额度的 Agent 路由与安全边界离线评测。"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from agent_core.workflow import AgentIntent, classify_intent

DEFAULT_DATASET = Path(__file__).with_name("eval") / "agent_cases.jsonl"


@dataclass(frozen=True)
class EvaluationCase:
    id: str
    category: str
    query: str
    expected_intent: AgentIntent


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
    return {
        "total": len(rows),
        "passed": passed_count,
        "accuracy_pct": round(passed_count / len(rows) * 100, 2),
        "category_accuracy_pct": category_scores,
        "failures": [row for row in rows if not row["passed"]],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="运行 Agent 离线路由评测")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, help="可选 JSON 报告路径")
    args = parser.parse_args()

    report = evaluate_routing(load_cases(args.dataset))
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["accuracy_pct"] >= 90 else 1


if __name__ == "__main__":
    raise SystemExit(main())
