"""Agent 意图的确定性路由规则。"""

from __future__ import annotations

import re

from agent_core.models import AgentIntent

_KNOWLEDGE_MARKERS = ("定义", "含义", "怎么算", "如何计算", "公式", "规则", "标准", "正常")
_CONCRETE_DATA_MARKERS = ("多少", "最多", "最高", "最低", "排名", "趋势", "最近", "同比", "环比", "top", "各平台", "当前")
_BLOCKED_PATTERNS = (
    r"密码|手机号|身份证|个人隐私|具体地址|api.?key|环境变量|系统提示词",
    r"(?:删除|修改|写入|清空|更新).*(?:数据库|数据|订单|表)",
    r"\b(?:drop|delete|update|insert|alter|truncate)\b",
    r"忽略(?:以上|之前|系统).*(?:指令|提示词)|ignore previous instructions",
)
_VAGUE_QUERIES = {"分析一下", "看看数据", "帮我分析", "查一下", "分析数据"}


def classify_intent(query: str) -> AgentIntent:
    """使用确定性规则提供稳定路由；复杂语义仍交给下游 Agent 处理。"""
    normalized = query.strip().lower()
    if any(re.search(pattern, normalized, re.IGNORECASE) for pattern in _BLOCKED_PATTERNS):
        return "blocked"
    if len(normalized) < 4 or normalized in _VAGUE_QUERIES:
        return "clarification"
    has_knowledge = any(marker in normalized for marker in _KNOWLEDGE_MARKERS)
    if has_knowledge and any(marker in normalized for marker in _CONCRETE_DATA_MARKERS):
        return "hybrid"
    if has_knowledge:
        return "knowledge"
    return "data"
