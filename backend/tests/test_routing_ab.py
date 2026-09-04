"""路由 A/B 基线的回归测试。

锁定三层数字（2026-09-04 实测）：
- curated 100 条：规则路由下限 ≥97%（当前 100%）；
- robustness（dev，25 条，参与过调优）：加固后下限 ≥92%（当前 96%，含 1 条 gold 存疑用例）；
- heldout（10 条，调优前冻结）：真实泛化下限 ≥50%（当前 60%），
  残留缺口（导出客户资料/收货地址/记录行/泛宾语盘点）为下一轮加固 backlog。
LLM 侧不在此处运行（需密钥，由 ab_routing_eval.py 承担）。
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
HELDOUT = _load("routing_robustness_heldout.jsonl")


def _acc(cases: list[dict]) -> float:
    return sum(1 for c in cases if classify_intent(c["query"]) == c["expected_intent"]) / len(cases)


def test_rule_router_curated_baseline():
    # curated（贴合标记词）集防回归下限
    assert _acc(CURATED) >= 0.97


def test_robustness_dev_floor_after_hardening():
    # dev 集加固后下限：口语改写/隐私变体/注入改写应保持可拦截
    assert len(ROBUST) >= 20
    assert _acc(ROBUST) >= 0.92


def test_heldout_generalization_floor():
    # 留出集（冻结 gold）真实泛化下限；当前 60%，缺口已入加固 backlog
    assert len(HELDOUT) >= 10
    assert _acc(HELDOUT) >= 0.5
