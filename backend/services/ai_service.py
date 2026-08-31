import asyncio
import json
import logging
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from langchain_community.utilities.sql_database import SQLDatabase
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from sqlalchemy import text

from agent_core import AgentRuntime
from agent_core.models import ModelResponse
from agent_core.rag import MarkdownKnowledgeRetriever
from agent_core.session import FallbackConversationStore, MemoryConversationStore, RedisConversationStore
from backend.config import get_settings
from backend.models.schemas import AIQueryResponse, AgentUsage
from backend.utils.sql_guard import guard_read_only_engine, is_read_only_sql

logger = logging.getLogger(__name__)

settings = get_settings()

BUSINESS_CONTEXT = """## 数据时间范围
- 数据时间范围：2025-01-01 至 2025-12-31（共1年数据）
- 当用户提到"最近N天"时，指的是数据中的最近N天

## 业务指标定义
- 付款金额 = 实际销售额（非订单金额）
- 平台类型枚举值：APP、微信公众号、Web网站、其他
- 是否退款：是=已退款，否=未退款
- 退款率 = 退款订单数 / 总订单数
- 复购率 = 消费2次及以上的用户数 / 总用户数
- 客单价 = 总付款金额 / 总订单数

## 回答规则
1. 始终先查看表结构确认列名，再编写 SQL
2. 日期筛选使用 order_date 列，格式 'YYYY-MM-DD'
3. 金额查询使用 payment_amount
4. 退款相关使用 is_refund = '是'（注意：is_refund 是物理列名，
   ORM 属性名是 is_refunded，本提示词面向原生 SQL，必须用物理列名 is_refund）
5. SQL 结果较大时使用 LIMIT 限制
6. 先给出数据结论，再附上 SQL 语句
7. 用中文回答
8. 仅回答电商数据相关问题"""


def _detect_chart_type(columns: list[str], rows: list) -> str | None:
    if not rows or len(columns) < 2:
        return None
    col1 = columns[0].lower()
    time_keywords = ['date', '时间', 'time', 'hour', '日期', '月']
    if any(k in col1 for k in time_keywords):
        return "line"
    if len(rows) <= 6:
        return "pie"
    return "bar"


def _build_visualization(columns: list[str], rows: list) -> dict | None:
    chart_type = _detect_chart_type(columns, rows)
    if not chart_type:
        return None
    return {
        "chart_type": chart_type,
        "x_field": columns[0],
        "y_field": columns[1] if len(columns) > 1 else None,
        "data": [dict(zip(columns, row)) for row in rows] if rows else [],
    }


def _json_safe_value(value):
    """把数据库类型转换为 API 可稳定序列化的基础类型。"""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _execute_query_with_columns(sql: str) -> list[dict]:
    """执行只读 SQL，并直接使用数据库返回的列名映射结果。

    不再从 SELECT 文本中按逗号猜测列名；CASE、ROUND 等复杂表达式内部
    也包含逗号，字符串切分会导致列名与结果错位。
    """
    if not is_read_only_sql(sql):
        raise ValueError("仅允许执行只读 SQL")

    db = _get_sync_db()
    with db._engine.connect() as connection:
        rows = connection.execute(text(sql)).mappings().all()
    return [
        {str(key): _json_safe_value(value) for key, value in row.items()}
        for row in rows
    ]


@lru_cache(maxsize=1)
def _get_sync_db() -> SQLDatabase:
    # 优先使用只读账户（部署环境为 ea_ai）：即使只读黑名单被绕过也无法写库。
    # 连接串组件统一走 quote_plus，密码含 @:/ 等字符时不会被污染。
    db = SQLDatabase.from_uri(
        settings.ai_database_url,
        engine_args={
            "pool_pre_ping": True,
            "pool_size": 3,
            "max_overflow": 2,
            "pool_recycle": 3600,
        },
    )
    guard_read_only_engine(db._engine)
    return db


class _SQLPlan(BaseModel):
    sql: str = Field(description="一条只读 MySQL SELECT 或 WITH 查询，不包含 Markdown")


def _model_response(message) -> ModelResponse:
    usage = getattr(message, "usage_metadata", None) or {}
    return ModelResponse(
        content=str(message.content),
        input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
        total_tokens=usage.get("total_tokens"),
    )


def _runtime_llm() -> ChatOpenAI:
    if not settings.llm_api_key:
        raise RuntimeError("模型未配置")
    return ChatOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        temperature=0,
        timeout=120,
        max_retries=1,
    )


_knowledge_retriever = MarkdownKnowledgeRetriever(
    Path(__file__).resolve().parents[2] / "ai-ecommerce-assistant" / "knowledge_base"
)


async def _runtime_retrieve(query: str):
    return await _knowledge_retriever.retrieve(query, top_k=3)


async def _runtime_schema() -> str:
    return await asyncio.to_thread(_get_sync_db().get_table_info, ["orders"])


async def _runtime_generate_sql(query, schema, history, sources, previous_error) -> ModelResponse:
    source_context = "\n".join(f"{item.section}: {item.snippet}" for item in sources)
    history_context = json.dumps(history[-6:], ensure_ascii=False)
    prompt = f"""你是只读电商 Text-to-SQL 模块。只返回结构化 sql 字段。
{BUSINESS_CONTEXT}

表结构：
{schema}

知识来源：
{source_context or '无'}

最近会话：{history_context}
用户问题：{query}
上次脱敏错误：{previous_error or '无'}

必须生成单条 SELECT/WITH 查询，不得写库，不得查询个人隐私。"""
    structured = _runtime_llm().with_structured_output(_SQLPlan, include_raw=True)
    response = await structured.ainvoke(prompt)
    parsed = response.get("parsed") if isinstance(response, dict) else None
    if parsed is None:
        raise ValueError("模型未返回合法的结构化 SQL")
    raw = response.get("raw")
    model = _model_response(raw) if raw is not None else ModelResponse(content="")
    model.content = parsed.sql
    return model


async def _runtime_execute(sql: str) -> list[dict]:
    # AST 层之后仍保留执行器黑名单与数据库只读账户两层防护。
    return await asyncio.to_thread(_execute_query_with_columns, sql)


async def _runtime_answer(query, intent, history, sources, sql, rows) -> ModelResponse:
    if not settings.llm_api_key:
        if sources:
            summary = "\n".join(f"- {item.section}：{item.snippet}" for item in sources)
            return ModelResponse(f"当前未配置模型，已返回最相关的业务知识：\n{summary}")
        return ModelResponse("⚠️ AI功能未配置，请在 .env 中设置 LLM_API_KEY。")
    source_context = "\n".join(
        f"[{item.filename} / {item.section}] {item.snippet}" for item in sources
    )
    prompt = f"""你是电商数据分析助手。根据已验证的工具结果用中文简洁回答，不得编造。
问题：{query}
意图：{intent}
最近会话：{json.dumps(history[-6:], ensure_ascii=False)}
引用知识：{source_context or '无'}
SQL：{sql or '未执行'}
结果：{json.dumps(rows[:50], ensure_ascii=False)}
若结果为空，请明确说明；引用知识时说明来源文件和章节。"""
    return _model_response(await _runtime_llm().ainvoke(prompt))


def _conversation_store():
    memory = MemoryConversationStore(ttl_seconds=1800, max_sessions=1000, max_turns=6)
    primary = RedisConversationStore(settings.redis_url) if settings.redis_enabled else None
    return FallbackConversationStore(primary, memory)


_runtime = AgentRuntime(
    retriever=_runtime_retrieve,
    schema_loader=_runtime_schema,
    sql_generator=_runtime_generate_sql,
    sql_executor=_runtime_execute,
    answer_generator=_runtime_answer,
    conversations=_conversation_store(),
    sql_timeout_seconds=10,
)


async def process_natural_language_query(
    query: str,
    thread_id: str | None = None,
    *,
    owner: str = "anonymous",
) -> AIQueryResponse:
    """使用共享分节点 Runtime，并转换为向后兼容的 API 响应。"""
    state = await _runtime.invoke(query, owner=owner, thread_id=thread_id)
    result = state["result"]
    visualization = None
    if result.rows:
        columns = list(result.rows[0])
        visualization = _build_visualization(columns, [list(item.values()) for item in result.rows])
    return AIQueryResponse(
        sql=result.sql,
        result=result.rows,
        answer=result.answer,
        visualization=visualization,
        sql_error=result.sql_error,
        request_id=state["request_id"],
        thread_id=state["thread_id"],
        intent=result.intent,
        sources=[
            {
                "filename": item.filename,
                "section": item.section,
                "doc_type": item.doc_type,
                "score": item.score,
                "snippet": item.snippet,
            }
            for item in result.sources
        ],
        steps=[
            {
                "name": item.name,
                "status": item.status,
                "duration_ms": item.duration_ms,
                "summary": item.summary,
            }
            for item in result.steps
        ],
        usage=AgentUsage(
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            total_tokens=result.usage.total_tokens,
            latency_ms=result.usage.latency_ms,
        ) if result.usage else None,
    )
