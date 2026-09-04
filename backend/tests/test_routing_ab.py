"""路由 A/B 基线的回归测试。

锁定确定性规则路由在 curated 集上的表现，并确认 robustness 子集存在且规则侧会显著退化
（以此佐证 LLM 路由对照研究的必要性）。LLM 侧不在此处运行（需密钥，由 ab_routing_eval.py 承担）。
"""

import json
from pathlib import Path

from agent_core.routing import classify_intent

EVAL_DIR = Path(__file__).resolve().parents[2] / "agent_core" / "eval"


def _load(name: str) -> list[dict]:
    return [
        json.loads(line)
        for line in (EVAL_DIR / name).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


CURATED = _load("agent_cases.jsonl")
ROBUST = _load("routing_robustness.jsonl")


def _acc(cases: list[dict]) -> float:
    return sum(1 for c in cases if classify_intent(c["query"]) == c["expected_intent"]) / len(cases)


def test_rule_router_currated_baseline():
    # 规则路由在 curated（贴合标记词）集上应接近满分；锁定回归下限
    assert _acc(CURATED) >= 0.97


def test_robustness_set_exists_and_rules_degrade():
    # robustness 子集必须存在；规则路由在该集上应明显退化（证明其脆弱性）
    assert len(ROBUST) >= 20
    # 当前经验值约 0.24；若未来强化规则使该值上升，说明泛化改善，断言仍成立
    assert _acc(ROBUST) < 0.95
