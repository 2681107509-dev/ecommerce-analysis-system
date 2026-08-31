"""可解释的 Agent 状态图：统一输入检查、路由、执行和轨迹输出。"""

from __future__ import annotations

import re
import time
from collections.abc import Awaitable, Callable
from typing import Any, Literal, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

AgentIntent = Literal["data", "knowledge", "hybrid", "clarification", "blocked"]
Executor = Callable[[str], Awaitable[Any]]

_KNOWLEDGE_MARKERS = ("定义", "含义", "怎么算", "如何计算", "公式", "规则", "标准", "正常")
_CONCRETE_DATA_MARKERS = ("多少", "最多", "最高", "最低", "排名", "趋势", "最近", "同比", "环比", "top", "各平台", "当前")
_BLOCKED_PATTERNS = (
    r"密码|手机号|身份证|个人隐私|具体地址|api.?key|环境变量|系统提示词",
    r"(?:删除|修改|写入|清空|更新).*(?:数据库|数据|订单|表)",
    r"\b(?:drop|delete|update|insert|alter|truncate)\b",
    r"忽略(?:以上|之前|系统).*(?:指令|提示词)|ignore previous instructions",
)
_VAGUE_QUERIES = {"分析一下", "看看数据", "帮我分析", "查一下", "分析数据"}


class AgentState(TypedDict, total=False):
    query: str
    request_id: str
    thread_id: str
    intent: AgentIntent
    result: Any
    steps: list[dict[str, Any]]


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


def _step(name: str, started: float, summary: str, status: str = "success") -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "duration_ms": max(0, round((time.perf_counter() - started) * 1000)),
        "summary": summary,
    }


class AgentWorkflow:
    """在业务执行器外增加稳定、可测试且不泄露思维链的状态图。"""

    def __init__(self, executor: Executor):
        self._executor = executor
        graph = StateGraph(AgentState)
        graph.add_node("route", self._route)
        graph.add_node("execute", self._execute)
        graph.add_node("respond_without_execution", self._respond_without_execution)
        graph.add_edge(START, "route")
        graph.add_conditional_edges(
            "route",
            lambda state: "stop" if state["intent"] in {"blocked", "clarification"} else "execute",
            {"stop": "respond_without_execution", "execute": "execute"},
        )
        graph.add_edge("execute", END)
        graph.add_edge("respond_without_execution", END)
        self._graph = graph.compile()

    async def _route(self, state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        intent = classify_intent(state["query"])
        steps = [*state.get("steps", []), _step("route", started, f"识别为 {intent} 类型问题")]
        return {"intent": intent, "steps": steps}

    async def _execute(self, state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            result = await self._executor(state["query"])
            event = _step("agent_execute", started, "完成模型工具调用与只读数据查询")
        except Exception:
            event = _step("agent_execute", started, "Agent 执行失败", status="error")
            raise
        return {"result": result, "steps": [*state.get("steps", []), event]}

    async def _respond_without_execution(self, state: AgentState) -> dict[str, Any]:
        from agent_core.models import AgentResult

        started = time.perf_counter()
        if state["intent"] == "blocked":
            answer = "⚠️ 仅支持聚合分析和只读查询，不能提供隐私数据或修改数据库。"
        else:
            answer = "请补充要分析的指标、时间范围或维度，例如“最近30天各平台销售额趋势”。"
        result = AgentResult(answer=answer)
        event = _step("safe_response", started, "未调用模型和数据库，返回安全澄清响应")
        return {"result": result, "steps": [*state.get("steps", []), event]}

    async def invoke(self, query: str, thread_id: str | None = None) -> AgentState:
        return await self._graph.ainvoke(
            {
                "query": query.strip(),
                "request_id": str(uuid4()),
                "thread_id": thread_id or str(uuid4()),
                "steps": [],
            }
        )
