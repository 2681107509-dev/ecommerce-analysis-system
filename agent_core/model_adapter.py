"""兼容 OpenAI 接口的共享模型适配器。"""

from __future__ import annotations

import json

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from agent_core.models import AgentIntent, AgentSource, ModelResponse
from agent_core.session import Message


class _SQLPlan(BaseModel):
    sql: str = Field(description="一条只读 SQL SELECT 或 WITH 查询，不包含 Markdown")


def _response(message) -> ModelResponse:
    usage = getattr(message, "usage_metadata", None) or {}
    return ModelResponse(
        content=str(message.content),
        input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
        total_tokens=usage.get("total_tokens"),
    )


class OpenAIModelAdapter:
    def __init__(self, *, api_key: str, base_url: str, model: str, business_context: str):
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._business_context = business_context

    def _client(self) -> ChatOpenAI:
        if not self._api_key:
            raise RuntimeError("模型未配置")
        return ChatOpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            model=self._model,
            temperature=0,
            timeout=120,
            max_retries=1,
        )

    async def generate_sql(
        self,
        query: str,
        schema: str,
        history: list[Message],
        sources: list[AgentSource],
        previous_error: str | None,
    ) -> ModelResponse:
        source_context = "\n".join(f"{item.section}: {item.snippet}" for item in sources)
        prompt = f"""你是只读电商 Text-to-SQL 模块。只返回结构化 sql 字段。
{self._business_context}

表结构：
{schema}

知识来源：
{source_context or '无'}

最近会话：{json.dumps(history[-6:], ensure_ascii=False)}
用户问题：{query}
上次脱敏错误：{previous_error or '无'}

必须生成单条 SELECT/WITH 查询，不得写库，不得查询个人隐私。"""
        response = await self._client().with_structured_output(_SQLPlan, include_raw=True).ainvoke(prompt)
        parsed = response.get("parsed") if isinstance(response, dict) else None
        if parsed is None:
            raise ValueError("模型未返回合法的结构化 SQL")
        raw = response.get("raw")
        model_response = _response(raw) if raw is not None else ModelResponse(content="")
        model_response.content = parsed.sql
        return model_response

    async def answer(
        self,
        query: str,
        intent: AgentIntent,
        history: list[Message],
        sources: list[AgentSource],
        sql: str | None,
        rows: list[dict],
    ) -> ModelResponse:
        if not self._api_key:
            if sources:
                summary = "\n".join(f"- {item.section}：{item.snippet}" for item in sources)
                return ModelResponse(f"当前未配置模型，已返回最相关的业务知识：\n{summary}")
            return ModelResponse("⚠️ AI功能未配置，请配置模型 API Key。")
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
        return _response(await self._client().ainvoke(prompt))

    def test_connection(self) -> None:
        if not self._api_key:
            raise RuntimeError("模型未配置")
        ChatOpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            model=self._model,
            temperature=0,
            timeout=15,
            max_retries=0,
            max_tokens=1,
        ).invoke("仅回复 OK")
