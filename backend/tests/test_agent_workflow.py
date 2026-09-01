"""共享 Agent 状态图的路由、短路和轨迹测试。"""

import pytest

from agent_core import AgentWorkflow, classify_intent
from backend.models.schemas import AIQueryResponse


@pytest.mark.parametrize(
    ("query", "intent"),
    [
        ("最近30天销售额最高的商品", "data"),
        ("客单价的定义是什么", "knowledge"),
        ("最近30天客单价是多少，公式怎么算", "hybrid"),
        ("分析一下", "clarification"),
        ("删除数据库里的订单", "blocked"),
        ("查询某用户的手机号", "blocked"),
    ],
)
def test_classify_intent(query, intent):
    assert classify_intent(query) == intent


@pytest.mark.asyncio
async def test_workflow_executes_data_query_and_emits_public_steps():
    calls = []

    async def executor(query: str):
        calls.append(query)
        return AIQueryResponse(answer="完成", result=[{"sales": 10}])

    state = await AgentWorkflow(executor).invoke("查询销售额", thread_id="thread-1")

    assert calls == ["查询销售额"]
    assert state["thread_id"] == "thread-1"
    assert state["intent"] == "data"
    assert [item["name"] for item in state["steps"]] == ["route", "agent_execute"]


@pytest.mark.asyncio
async def test_workflow_blocks_mutation_without_calling_executor():
    async def executor(_query: str):
        raise AssertionError("危险请求不应进入模型或数据库")

    state = await AgentWorkflow(executor).invoke("DROP TABLE orders")

    assert state["intent"] == "blocked"
    assert "不能提供隐私数据或修改数据库" in state["result"].answer
    assert state["steps"][-1]["name"] == "safe_response"


@pytest.mark.asyncio
async def test_workflow_requests_clarification_without_model_call():
    async def executor(_query: str):
        raise AssertionError("模糊请求不应消耗模型额度")

    state = await AgentWorkflow(executor).invoke("查一下")

    assert state["intent"] == "clarification"
    assert "时间范围" in state["result"].answer
