import asyncio
import datetime
import decimal
import hashlib
import html
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote_plus
from uuid import uuid4

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# 复用 backend 的共享工具（clean_sql），保证两处实现一致
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
# 业务知识来源抽取（无 streamlit 依赖，便于单元测试）
# 注意：rag.* 子模块的顶层 import 会立刻拉起 BGE + Chroma（embedding + 持久化客户端），
# 严重拖慢 Streamlit 冷启动。RAG 仅在知识类问题处理路径才需要，
# 因此把 from rag import metrics 挪到使用处（条件块内）——首次启用事件落盘时才付代价。

from agent_core import AgentRuntime
from agent_core.db_schema import describe_table
from agent_core.model_adapter import OpenAIModelAdapter
from agent_core.models import AgentSource
from agent_core.session import MemoryConversationStore
from agent_core.sql_safety import dialect_from_url
from backend.utils.sql_guard import (
    ensure_read_only_sql,
    guard_read_only_engine,
)
from backend.utils.text_cleaner import clean_sql, sanitize_error

load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

logger = logging.getLogger(__name__)

# 用户反馈落盘路径（jsonl，append-only）
FEEDBACK_LOG_PATH = os.environ.get(
    "RAG_FEEDBACK_PATH",
    str(Path(__file__).resolve().parent / "eval" / "feedback.jsonl"),
)

# 启用 RAG 事件 JSONL 落盘（默认关闭磁盘 IO，避免拖慢；可由环境变量开启）
if os.environ.get("RAG_EVENTS_LOG", "0") == "1":
    from rag import metrics as rag_metrics  # 仅在真正启用时付一次导入代价
    rag_metrics.enable_event_file_logging()


def record_feedback(question: str, answer: str, rating: str,
                    rag_sources: list[dict] | None = None) -> bool:
    """把用户赞成/反对反馈追加到 jsonl 文件，供离线分析检索质量。

    Args:
        question: 用户问题。
        answer: AI 回答（前 500 字符，避免文件膨胀）。
        rating: "up" 或 "down"。
        rag_sources: 本次回答引用的业务知识来源（用于线下分析"误检索"）。

    Returns:
        是否落盘成功。
    """
    payload = {
        "ts": int(time.time() * 1000),
        "question": question[:300],
        "answer_preview": answer[:500],
        "rating": rating,
        "rag_sources_count": len(rag_sources or []),
        "rag_filenames": [s.get("filename", "") for s in (rag_sources or [])],
    }
    try:
        p = Path(FEEDBACK_LOG_PATH)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return True
    except Exception as e:
        logger.warning("反馈落盘失败: %s", e)
        return False

API_KEY = os.getenv("LLM_API_KEY")
BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
MODEL_NAME = os.getenv("LLM_MODEL", "deepseek-chat")

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "ai_commerce_intelligence_platform")

USE_MYSQL = bool(DB_USER and DB_PASSWORD)

BUSINESS_CONTEXT = """## 数据时间范围
- 数据时间范围：2025-01-01 至 2025-12-31（共1年数据）
- 当前日期：2026年（数据截止到2025年12月31日）
- 【重要】当用户提到"最近N天"时，指的是数据中的最近N天，而非当前日期

## 业务指标定义
- 付款金额 = 实际销售额（非订单金额）
- 平台类型枚举值：APP、微信公众号、Web网站、其他
- 是否退款：是=已退款，否=未退款
- 退款率 = 退款订单数 / 总订单数
- 复购率 = 消费2次及以上的用户数 / 总用户数
- 客单价 = 总付款金额 / 总订单数
- 数据起止日期仅用于解释“最近”问题；用户未指定时间时，禁止添加 order_time/order_date 条件或全年过滤
- 订单量必须使用 COUNT(DISTINCT order_id)，禁止使用 COUNT(*)
- 除非用户明确要求排除退款，否则销售额、订单量、用户数等指标包含退款订单
- 用户明确指定月份或日期时必须严格使用该范围，不得扩大为全年
- RFM 分层阈值：Recency≤30天为活跃，Frequency≥2次为高频，Monetary≥1500元为高价值
- 下单小时：0-23，高峰时段为 11-13 时和 19-21 时
- 星期几：周一至周日

## 回答规则
1. 始终先查看表结构确认列名，再编写 SQL
2. 日期筛选使用 order_date 列，格式 'YYYY-MM-DD'
3. 【重要】当用户提到"最近N天"时，自动替换为数据中的最近N天。例如：
   - "最近7天" → 数据中最近7天：2025-12-25 至 2025-12-31
   - "最近30天" → 数据中最近30天
4. 金额查询使用 payment_amount（实际付款金额）
5. 退款相关使用 is_refund = '是' 表示已退款
6. SQL 结果较大时使用 LIMIT 限制
7. 先给出数据结论，再附上 SQL 语句
8. 用中文回答
9. 仅回答电商数据相关问题
10. 如果发现某指标明显异常（如某渠道退款率远超平均值），请在回答末尾添加【异常预警】段落，给出业务建议"""

SENSITIVE_PATTERNS = [
    r"密码", r"手机号", r"身份证", r"地址.*具体", r"订单明细.*用户名",
    r"个人.*信息", r"隐私", r"password", r"phone.*number",
]

SENSITIVE_RESPONSE = "该数据已脱敏，仅支持聚合查询，无法提供用户个人隐私数据。"


def is_sensitive_query(query: str) -> bool:
    for pattern in SENSITIVE_PATTERNS:
        if re.search(pattern, query, re.IGNORECASE):
            return True
    return False


def get_cache_key(question: str) -> str:
    return hashlib.md5(question.encode()).hexdigest()


st.set_page_config(page_title="AI Commerce Intelligence Platform", layout="wide",
                   initial_sidebar_state="expanded")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Noto+Sans+SC:wght@400;500;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

    :root {
        --brand: #1565C0;
        --teal: #14B8A6;
        --purple: #8B5CF6;
        --orange: #F97316;
        --green: #22C55E;
        --bg: #F6F8FC;
        --surface: #FFFFFF;
        --surface-2: #F8FAFC;
        --sidebar: #EEF2F7;
        --line: #E2E8F0;
        --line-strong: #CBD5E1;
        --ink: #0F172A;
        --muted: #64748B;
        --sans: 'Manrope', 'Noto Sans SC', -apple-system, 'Segoe UI', 'Microsoft YaHei', sans-serif;
        --mono: 'JetBrains Mono', 'Cascadia Code', Consolas, monospace;
    }

    html, body, [class*="css"] { font-family: var(--sans); }
    .stApp { background: var(--bg); color: var(--ink); }
    .block-container { max-width: 1380px; padding-top: 2rem; padding-bottom: 7rem; }
    [data-testid="stHeader"] { background: var(--bg); border-bottom: 1px solid rgba(226,232,240,.7); }
    [data-testid="stSidebar"] {
        min-width: 300px; max-width: 340px; background: var(--sidebar); color: var(--ink);
        border-right: 1px solid var(--line);
    }
    [data-testid="stSidebar"] .stMarkdown,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] label { color: var(--ink); }
    [data-testid="stChatMessage"] {
        background: var(--surface); border: 1px solid var(--line); border-radius: 14px;
        padding: .8rem 1rem; box-shadow: none;
    }
    [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] { line-height: 1.68; }
    [data-testid="stChatInput"] {
        border: 1px solid var(--line-strong); border-radius: 14px; background: var(--surface);
        box-shadow: none;
    }
    [data-testid="stChatInput"]:focus-within {
        border-color: var(--brand); box-shadow: 0 0 0 2px rgba(21,101,192,.14);
    }
    h1, h2, h3 { color: var(--ink); letter-spacing: -.02em; font-family: var(--sans); }
    h1 { font-size: clamp(2rem, 3vw, 2.6rem); font-weight: 800; }
    h2, h3 { font-weight: 750; }
    .stCaption, [data-testid="stCaptionContainer"] { color: var(--muted); }
    .stButton > button, [data-testid="stFormSubmitButton"] > button, [data-testid="stDownloadButton"] > button {
        border-radius: 10px; border: 1px solid var(--line-strong); background: var(--surface);
        color: var(--ink); font-weight: 650; box-shadow: none; transition: background .15s, border-color .15s;
    }
    .stButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover,
    [data-testid="stDownloadButton"] > button:hover { background: var(--surface-2); border-color: #94A3B8; }
    .stButton > button:focus-visible, [data-testid="stFormSubmitButton"] > button:focus-visible,
    [data-testid="stDownloadButton"] > button:focus-visible, [data-testid="stChatInput"] textarea:focus-visible {
        outline: 2px solid rgba(21,101,192,.34); outline-offset: 2px;
    }
    [data-testid="stExpander"] {
        background: var(--surface); border: 1px solid var(--line); border-radius: 10px; box-shadow: none;
    }
    [data-testid="stAlert"] { border-radius: 10px; box-shadow: none; }
    [data-testid="stMetric"] {
        background: var(--surface); border: 1px solid var(--line); border-radius: 10px;
        padding: 12px 14px; box-shadow: none;
    }
    [data-testid="stMetricValue"] { font-family: var(--mono); font-variant-numeric: tabular-nums; }
    [data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }

    .status-strip {
        display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: 14px 0 18px;
    }
    .status-card {
        min-width: 0; background: var(--surface); border: 1px solid var(--line); border-radius: 10px;
        padding: 12px 14px;
    }
    .status-label {
        display: flex; align-items: center; gap: 7px; color: var(--muted); font-family: var(--mono);
        font-size: 10.5px; letter-spacing: 1px; text-transform: uppercase;
    }
    .status-dot { width: 7px; height: 7px; border-radius: 2px; flex: none; }
    .status-ok .status-dot { background: var(--green); }
    .status-warn .status-dot { background: var(--orange); }
    .status-error .status-dot { background: #DC2626; }
    .status-value {
        margin-top: 6px; color: var(--ink); font-weight: 750; font-size: 14px;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .status-note { margin-top: 3px; color: var(--muted); font-size: 12px; line-height: 1.45; }

    .setup-panel {
        background: var(--surface); border: 1px solid var(--line); border-radius: 14px;
        padding: 18px 20px; margin: 12px 0 18px;
    }
    .setup-title { color: var(--ink); font-size: 18px; font-weight: 800; letter-spacing: -.02em; }
    .setup-body { color: var(--muted); font-size: 14px; line-height: 1.7; margin-top: 7px; }
    .setup-actions { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }
    .setup-action {
        min-width: 0; background: var(--surface-2); border: 1px solid var(--line); border-radius: 10px;
        padding: 11px 12px;
    }
    .setup-step { color: var(--brand); font-family: var(--mono); font-size: 11px; font-weight: 700; }
    .setup-action strong { display: block; color: var(--ink); font-size: 13px; margin-top: 4px; }
    .setup-action span:last-child { display: block; color: var(--muted); font-size: 12px; line-height: 1.45; margin-top: 3px; }

    .step-indicator {
        display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
        padding: 11px 13px; border-radius: 10px;
        background: var(--surface-2); border: 1px solid var(--line); margin-bottom: 12px;
    }
    .step-item { font-size: 13px; font-family: var(--mono); font-variant-numeric: tabular-nums; }
    .step-done { color: #15803D; }
    .step-active { color: var(--brand); font-weight: 700; }
    .step-error { color: #DC2626; font-weight: 700; }
    .step-pending { color: #94A3B8; }
    .highlight-num { color: var(--brand); font-weight: 750; font-variant-numeric: tabular-nums; }
    .warning-box {
        background: rgba(249,115,22,0.08); border: 1px solid rgba(249,115,22,0.22);
        color: #9A3412; padding: 10px 13px; border-radius: 8px; margin: 8px 0;
    }
    .sql-block {
        position: relative; background: #0F172A; border: 1px solid #1E293B; border-radius: 10px;
        padding: 14px; margin: 10px 0 6px; font-family: var(--mono);
        font-size: 13px; overflow-x: auto;
    }
    .sql-copy-btn {
        position: absolute; top: 8px; right: 8px;
        background: rgba(20,184,166,0.14); border: 1px solid rgba(20,184,166,0.38);
        color: #CCFBF1; padding: 3px 9px; border-radius: 6px;
        cursor: pointer; font-size: 11px; font-family: var(--mono);
    }
    .sql-copy-btn:hover { background: rgba(20,184,166,0.24); }
    .query-time {
        color: var(--muted); font-size: 12px; margin-top: 4px;
        font-family: var(--mono); font-variant-numeric: tabular-nums;
    }
    .history-item {
        padding: 6px 10px; border-radius: 6px; margin-bottom: 4px;
        background: rgba(21,101,192,0.07); cursor: pointer;
        transition: background 0.2s; font-size: 13px;
    }
    .history-item:hover { background: rgba(21,101,192,0.13); }
    ::selection { background: rgba(21,101,192,.16); }
    * { scrollbar-width: thin; scrollbar-color: #CBD5E1 transparent; }
    *::-webkit-scrollbar { width: 10px; height: 10px; }
    *::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 999px; border: 3px solid transparent; background-clip: content-box; }
    *::-webkit-scrollbar-track { background: transparent; }

    @media (max-width: 760px) {
        .block-container { padding-left: 1rem; padding-right: 1rem; padding-top: 1.2rem; }
        .status-strip, .setup-actions { grid-template-columns: 1fr; }
        [data-testid="stMarkdownContainer"] h1 { font-size: 1.65rem !important; }
        [data-testid="stChatMessage"] { border-radius: 12px; }
    }
</style>
""", unsafe_allow_html=True)

st.title("AI 智能商业分析平台")
st.caption("基于 LangGraph + RAG 的结构化 Text-to-SQL | 安全路由 → 只读查询 → 来源与轨迹可见")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "你好！我是你的数据分析助手。你可以问我：\n"
                       "- 销售额最高的 3 个商品编号和金额\n"
                       "- APP 和公众号哪个销售额高\n"
                       "- 用户复购率是多少",
            "chart_data": None, "chart_title": "", "csv_data": None,
            "sql": None, "query_time": None,
        }
    ]

if "query_cache" not in st.session_state:
    st.session_state.query_cache = {}

if "query_history" not in st.session_state:
    st.session_state.query_history = []

if "model_api_key" not in st.session_state:
    st.session_state.model_api_key = API_KEY or ""
if "model_base_url" not in st.session_state:
    st.session_state.model_base_url = BASE_URL
if "model_name" not in st.session_state:
    st.session_state.model_name = MODEL_NAME
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid4())


def get_db_uri():
    if USE_MYSQL:
        return (
            f"mysql+pymysql://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}"
            f"@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
        )
    db_path = os.path.join(os.path.dirname(__file__), "ecommerce.db")
    return f"sqlite:///{db_path}"


@st.cache_resource
def init_engine() -> Engine | None:
    """初始化受只读拦截器保护的 SQLAlchemy Engine。"""
    try:
        engine = create_engine(get_db_uri(), pool_pre_ping=True)
        guard_read_only_engine(engine)
        return engine
    except Exception as e:
        logger.warning("SQLAlchemy engine 初始化失败: %s", e, exc_info=True)
        st.warning(f"SQLAlchemy engine 初始化失败：{sanitize_error(e)}")
        return None


@st.cache_resource
def init_retriever():
    """初始化 RAG 检索器（懒加载，第一次调用时下载 BGE 模型 ~93MB）。

    Returns:
        (retriever, status_dict) 元组。status_dict 包含 ok / error / count。
    """
    try:
        from rag import Retriever, VectorStore, get_embeddings
        embed = get_embeddings()
        store = VectorStore(embedding=embed)
        retriever = Retriever(store, k=3, score_threshold=0.4)
        retriever.dump_stats()
        return retriever, {
            "ok": True,
            "error": None,
            "count": store.count(),
        }
    except Exception as e:
        logger.error("RAG 初始化失败: %s", e)
        return None, {
            "ok": False,
            "error": str(e),
            "count": 0,
        }


class _LazyRetriever:
    """RAG 检索器懒加载代理。

    关键设计：模块顶层 import app.py 时不会拉起 BGE/Chromadb。
    真正的初始化只发生在首次 knowledge 类问题触发 retrieve() 调用时。
    - status：与 init_retriever 的 status_dict 同形，但 ok=False 时 count=0
    - get_stats()：未初始化时返回空 dict（避免 NoneType 报错）
    - dump_stats()：未初始化时 no-op
    - retrieve()：未初始化时返回空列表（与旧逻辑 "if _retriever is None: return []" 对齐）
    """
    def __init__(self):
        self._inner = None
        self.status = {"ok": False, "error": "not initialized yet", "count": 0}
        self._initialized = False

    def _ensure(self):
        if self._initialized:
            return
        self._initialized = True
        try:
            inner, status = init_retriever()
            self._inner = inner
            self.status = status
        except Exception as e:
            logger.error("RAG 懒加载失败: %s", e)
            self.status = {"ok": False, "error": str(e), "count": 0}
            self._inner = None

    def retrieve(self, query: str, k: int = 3):
        self._ensure()
        if self._inner is None:
            return []
        return self._inner.retrieve(query, k=k)

    def get_stats(self) -> dict:
        self._ensure()
        if self._inner is None:
            return {}
        return self._inner.get_stats()

    def dump_stats(self) -> None:
        self._ensure()
        if self._inner is not None:
            self._inner.dump_stats()


def get_session_runtime(_engine, _retriever):
    """按当前 Streamlit 会话创建共享 Runtime；API Key 不进入全局缓存。"""
    api_key = st.session_state.get("model_api_key", "").strip()
    if _engine is None or not api_key:
        return None

    base_url = st.session_state.get("model_base_url", BASE_URL).strip()
    model_name = st.session_state.get("model_name", MODEL_NAME).strip()
    fingerprint = hashlib.sha256(f"{api_key}:{base_url}:{model_name}".encode()).hexdigest()
    if st.session_state.get("runtime_fingerprint") == fingerprint:
        return st.session_state.get("runtime_instance")

    model_adapter = OpenAIModelAdapter(
        api_key=api_key,
        base_url=base_url,
        model=model_name,
        business_context=BUSINESS_CONTEXT,
    )

    async def retrieve_knowledge(query: str) -> list[AgentSource]:
        if _retriever is None:
            return []
        docs = await asyncio.to_thread(_retriever.retrieve, query, k=3)
        return [
            AgentSource(
                filename=Path(item.get("metadata", {}).get("source", "unknown")).name,
                section=item.get("metadata", {}).get("section", ""),
                doc_type=item.get("metadata", {}).get("doc_type", "markdown"),
                score=float(item.get("score", 0)),
                snippet=re.sub(r"\\s+", " ", item.get("content", ""))[:240],
            )
            for item in docs
        ]

    async def load_schema() -> str:
        return await asyncio.to_thread(describe_table, _engine, "orders")

    async def execute_sql(sql: str) -> list[dict]:
        frame = await asyncio.to_thread(run_sql_query, sql)
        return [] if frame is None else frame.to_dict(orient="records")

    runtime = AgentRuntime(
        retriever=retrieve_knowledge,
        schema_loader=load_schema,
        sql_generator=model_adapter.generate_sql,
        sql_executor=execute_sql,
        answer_generator=model_adapter.astream_answer,
        conversations=MemoryConversationStore(ttl_seconds=1800, max_sessions=1, max_turns=6),
        sql_timeout_seconds=10,
        # get_db_uri() 在无 MySQL 环境会回落到 SQLite，方言必须按实际连接串判断。
        sql_dialect=dialect_from_url(get_db_uri()),
    )
    st.session_state.runtime_instance = runtime
    st.session_state.runtime_fingerprint = fingerprint
    return runtime


def render_runtime_status(db_engine, rag_status: dict) -> None:
    """在主区域展示模型、数据库、RAG 三类可观察状态，便于无 Key/降级时快速定位。"""
    has_key = bool(st.session_state.get("model_api_key", "").strip())
    db_ok = db_engine is not None
    rag_count = int(rag_status.get("count") or 0)
    rag_ready = bool(rag_status.get("ok")) and rag_count > 0
    items = [
        {
            "label": "MODEL",
            "state": "ok" if has_key else "warn",
            "value": st.session_state.get("model_name", MODEL_NAME) if has_key else "待配置",
            "note": "凭据仅保存在当前浏览器会话" if has_key else "在侧栏填写兼容 OpenAI API 的 Key",
        },
        {
            "label": "DATABASE",
            "state": "ok" if db_ok else "error",
            "value": ("MySQL" if USE_MYSQL else "SQLite") if db_ok else "不可用",
            "note": "只读连接已就绪" if db_ok else "检查数据库服务与环境变量",
        },
        {
            "label": "RAG",
            "state": "ok" if rag_ready else "warn",
            "value": f"{rag_count} chunks" if rag_ready else ("知识库为空" if rag_status.get("ok") else "已降级"),
            "note": "业务知识检索可用" if rag_ready else "纯 SQL 查询模式",
        },
    ]
    cards = []
    for item in items:
        cards.append(
            f'<div class="status-card status-{item["state"]}">'
            f'<div class="status-label"><span class="status-dot"></span>{item["label"]}</div>'
            f'<div class="status-value">{html.escape(str(item["value"]))}</div>'
            f'<div class="status-note">{html.escape(item["note"])}</div>'
            '</div>'
        )
    st.markdown(f'<div class="status-strip">{"".join(cards)}</div>', unsafe_allow_html=True)


def render_setup_guide(db_engine) -> None:
    """无 API Key 或数据库不可用时，在主区域给出可恢复的下一步。"""
    has_key = bool(st.session_state.get("model_api_key", "").strip())
    if has_key and db_engine is not None:
        return
    if db_engine is None:
        title = "数据库连接不可用"
        body = "页面仍可查看配置与历史状态；恢复数据库连接后即可继续发起只读查询。"
    else:
        title = "完成模型配置后开始查询"
        body = "当前处于无 Key 降级状态。配置兼容 OpenAI API 的模型后，助手会展示路由、检索、SQL 与结果证据。"
    st.markdown(f"""
    <div class="setup-panel">
        <div class="setup-title">{title}</div>
        <div class="setup-body">{body}</div>
        <div class="setup-actions">
            <div class="setup-action"><span class="setup-step">01</span><strong>配置模型</strong><span>在侧栏填写 Base URL、模型名称与 API Key。</span></div>
            <div class="setup-action"><span class="setup-step">02</span><strong>测试连接</strong><span>先验证模型可用性，再应用配置。</span></div>
            <div class="setup-action"><span class="setup-step">03</span><strong>检查状态</strong><span>确认数据库为只读可用，RAG 失败时自动降级。</span></div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def detect_chart_type(df: pd.DataFrame, question: str = "") -> str:
    if df is None or len(df) == 0 or len(df.columns) < 2:
        return "none"
    
    col1, col2 = df.columns[0], df.columns[1]
    
    try:
        pd.to_numeric(df[col2], errors='raise')
    except (ValueError, TypeError):
        return "none"
    
    question_lower = question.lower()
    col1_lower = col1.lower()
    col2_lower = col2.lower() if col2 else ""
    
    rank_keywords = ['top', '最高', '排名', '排行', r'前\d+', '销量最高', '销售额最高']
    if any(re.search(k, question_lower) for k in rank_keywords):
        return "bar"
    
    compare_keywords = ['哪个', '谁', '比较', '对比', 'vs', '更多', '更高', '更低', '差异']
    if any(k in question_lower for k in compare_keywords):
        return "bar"
    
    rate_keywords = ['退款率', '转化率', '点击率', '复购率', 'rate', 'ratio', '比例对比', '各.*率']
    if any(k in question_lower for k in rate_keywords) or \
       (any(k in col2_lower for k in ['rate', 'ratio', '率']) and len(df) > 2):
        return "bar_h"
    
    first_col_str = df[col1].astype(str)
    
    is_date_format = first_col_str.str.match(r'^\d{4}-\d{2}-\d{2}').any() or \
                     first_col_str.str.match(r'^\d{2}/\d{2}').any() or \
                     (first_col_str.str.contains(r'^(0?[1-9]|1[0-9]|2[0-3])$', regex=True).any() and len(df) >= 12)
    
    time_col_names = ['date', '时间', 'time', 'hour', 'weekday', '星期', 'month', '月', 'order_date', 'order_hour']
    
    time_keywords = ['每天', '每日', '趋势', '变化', '时间段', '24小时', '最近', '周', '月份']
    if is_date_format or \
       (any(k in col1_lower for k in time_col_names)) or \
       (any(k in question_lower for k in time_keywords) and not any(k in question_lower for k in ['top', '最高'])):
        return "line"
    
    share_keywords = ['占比', '份额', '构成', '组成', '分布情况', 'percent of total']
    if any(k in question_lower for k in share_keywords) and len(df) <= 8:
        return "pie"
    
    if len(df) <= 4:
        return "pie"
    
    return "bar"


_CHART_SEQUENCE = ["#1565C0", "#14B8A6", "#F97316", "#8B5CF6", "#64748B"]
_CHART_FONT = {
    "family": "Manrope, Noto Sans SC, Microsoft YaHei, sans-serif",
    "size": 13,
    "color": "#334155",
}
_CHART_HOVERLABEL = {
    "bgcolor": "#0F172A",
    "bordercolor": "#0F172A",
    "font": {
        "family": "Manrope, Noto Sans SC, Microsoft YaHei, sans-serif",
        "size": 12,
        "color": "#F8FAFC",
    },
}


def create_chart(df: pd.DataFrame, title: str = "", question: str = "") -> go.Figure | None:
    chart_type = detect_chart_type(df, question)
    
    if chart_type == "none":
        return None

    cols = df.columns.tolist()
    x_col, y_col = cols[0], cols[1]

    if not title or title == "undefined" or not title.strip():
        title = f"{y_col} 分析"

    if chart_type == "line":
        fig = px.line(df, x=x_col, y=y_col, template="plotly_white", title=title,
                      markers=True, color_discrete_sequence=[_CHART_SEQUENCE[0]])
        fig.update_traces(line_width=3, marker_size=8,
                          fill='tozeroy', fillcolor='rgba(21,101,192,0.08)')
        fig.add_scatter(x=df[x_col], y=df[y_col], mode='markers',
                        marker={"size": 9, "color": _CHART_SEQUENCE[1], "line": {"width": 2, "color": '#FFFFFF'}},
                        showlegend=False)

    elif chart_type == "pie":
        fig = px.pie(df, names=x_col, values=y_col, template="plotly_white", title=title,
                     hole=0.42, color_discrete_sequence=_CHART_SEQUENCE)
        fig.update_traces(textposition='inside', textinfo='percent+label',
                          textfont={"size": 12, "color": '#0F172A'},
                          hovertemplate='<b>%{label}</b><br>数值: %{value:,.2f}<br>占比: %{percent}<extra></extra>',
                          pull=[0.015] * len(df))

    elif chart_type in ["bar_h", "bar"]:
        df_plot = df.copy()

        try:
            df_plot[y_col] = pd.to_numeric(df_plot[y_col], errors='coerce')
        except Exception:
            pass

        if len(df_plot) > 8:
            df_plot = df_plot.nlargest(8, columns=y_col).reset_index(drop=True)

        n_items = len(df_plot)
        # 受控蓝青色板：高值用主蓝，低值逐步降为浅蓝，避免高饱和红色误导风险语义。
        bar_colors = ['#1565C0', '#1E88E5', '#42A5F5', '#64B5F6',
                      '#90CAF9', '#BBDEFB', '#D6E8FB', '#EAF3FC']

        def format_y_label(val):
            val_str = str(val).strip()
            if val_str.isdigit():
                hour_val = int(val_str)
                if 0 <= hour_val <= 23:
                    return f"{hour_val}时"
                elif hour_val >= 1 and hour_val <= 31:
                    return f"{hour_val}日"
            return val_str

        # 计算合适的图表高度：每项至少 85px + 标题区 + 边距，让条形更显著
        dynamic_height = max(550, 140 + n_items * 85)

        if chart_type == "bar_h":
            fig = go.Figure()
            for i in range(n_items):
                y_val = df_plot[y_col].iloc[i]
                x_raw = df_plot[x_col].iloc[i]
                x_label = format_y_label(x_raw)
                try:
                    y_num = float(y_val)
                    y_text = f'{y_num:,.0f}'
                except (ValueError, TypeError):
                    y_num = 0
                    y_text = str(y_val)

                fig.add_trace(go.Bar(
                    x=[y_num],
                    y=[x_label],
                    orientation='h',
                    name=x_label,
                    marker={
                        "color": bar_colors[i % len(bar_colors)],
                        "line": {"width": 0, "color": 'rgba(255,255,255,0)'},
                        "cornerradius": 4,
                    },
                    text=y_text,
                    textposition='outside',
                    textfont={"size": 13, "color": '#334155', "family": 'JetBrains Mono, monospace'},
                    hovertemplate=f'<b>{x_label}</b><br>%{{x:,.0f}}<extra></extra>',
                ))

            fig.update_layout(height=dynamic_height, barmode='group')

        else:
            df_sorted = df_plot.sort_values(by=y_col, ascending=True).reset_index(drop=True)
            fig = go.Figure()
            for i in range(n_items):
                y_val = df_sorted[y_col].iloc[i]
                x_raw = df_sorted[x_col].iloc[i]
                x_label = format_y_label(x_raw)
                try:
                    y_num = float(y_val)
                    y_text = f'{y_num:,.0f}'
                except (ValueError, TypeError):
                    y_num = 0
                    y_text = str(y_val)

                fig.add_trace(go.Bar(
                    x=[y_num],
                    y=[x_label],
                    orientation='h',
                    name=x_label,
                    marker={
                        "color": bar_colors[(n_items - 1 - i) % len(bar_colors)],
                        "line": {"width": 0, "color": 'rgba(255,255,255,0)'},
                        "cornerradius": 4,
                    },
                    text=y_text,
                    textposition='outside',
                    textfont={"size": 13, "color": '#334155', "family": 'JetBrains Mono, monospace'},
                    hovertemplate=f'<b>{x_label}</b><br>%{{x:,.0f}}<extra></extra>',
                ))

            fig.update_layout(height=dynamic_height, barmode='group')

    else:
        fig = go.Figure()

    fig.update_layout(
        title={"text": title, "x": 0.02, "xanchor": 'left', "y": 0.97, "yanchor": 'top',
                   "font": {"size": 17, "color": '#0F172A', "family": _CHART_FONT["family"]}},
        margin={"l": 80 if chart_type in ["bar_h", "bar"] else 30,
                    "r": 100 if chart_type in ["bar_h", "bar"] else 30,
                    "t": 70, "b": 50},
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='#FFFFFF',
        font=_CHART_FONT,
        hoverlabel=_CHART_HOVERLABEL,
        colorway=_CHART_SEQUENCE,
        showlegend=False,
        xaxis={
            "showgrid": False if chart_type in ["bar_h", "bar"] else True,
            "gridcolor": '#E2E8F0',
            "linecolor": '#CBD5E1',
            "zerolinecolor": '#CBD5E1',
            "showticklabels": False if chart_type in ["bar_h", "bar"] else True,
            "tickangle": -20 if chart_type == "line" else 0,
            "tickfont": {"size": 11, "color": '#64748B'},
            "zeroline": False,
            "range": [0, None] if chart_type in ["bar_h", "bar"] else None,
        },
        yaxis={
            "showgrid": True,
            "gridcolor": '#E2E8F0',
            "linecolor": '#CBD5E1',
            "zerolinecolor": '#CBD5E1',
            "tickfont": {"size": 11, "color": '#64748B'},
        },
        hovermode='closest',
        bargap=0.42,
    )

    return fig


def parse_data_from_answer(answer: str) -> pd.DataFrame | None:
    if not answer or not isinstance(answer, str):
        return None

    rows = []

    # 模式1：商品编号/平台 + 数值（最精确，优先匹配）
    # 匹配 "商品编号: PR000385 销售额: 481182" 或 "APP: 201单" 等
    patterns = [
        # 商品编号 PRxxxxx + 金额
        r'(?:^|\n|[-•|])\s*(PR\d{4,})[^\d]*(\d[\d,]*\.?\d*)',
        # 商品编号: xxx 格式
        r'(?:商品编号|产品编号|product_id)[^\w]*(PR\d+)[^\d]*(\d[\d,]*\.?\d*)',
        # 平台类型 + 数值
        r'(APP|微信公众号|网站|web|小程序|公众号)[^\d]{0,10}(\d[\d,]*\.?\d*)',
        # 中文键名: 值
        r'[-•|]\s*([^\d:：\n]{2,20}?)[：:]\s*([￥¥$]?\s*[\d,]+\.?\d*)',
        # 纯 key: value
        r'(\w+)\s*[：:]\s*([￥¥$]?\s*[\d,]+\.?\d*)\s*(?:元|单|%|)?',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, answer, re.IGNORECASE | re.MULTILINE)
        if matches and len(matches) >= 2:
            for match in matches:
                key = match[0].strip()
                value_str = re.sub(r'[^\d.]', '', match[1])
                try:
                    value = float(value_str) if value_str else None
                    if value is not None and value > 0 and not _is_garbled_key(key):
                        rows.append({'name': key, 'value': value})
                except (ValueError, TypeError):
                    continue
            if len(rows) >= 2:
                rows = _filter_outlier_rows(rows)
                if len(rows) >= 2:
                    return pd.DataFrame(rows)

    # 模式2：从上下文中提取（带关键词的数值）
    number_pattern = r'([\d,]+\.?\d*)\s*(?:元|单|%|)'
    all_numbers = re.findall(number_pattern, answer)

    if len(all_numbers) >= 3:
        keywords = ['PR', 'APP', '微信', '商品', '平台']
        for kw in keywords:
            if kw in answer:
                context_matches = re.findall(rf'({kw}[^0-9\n]*?)(?:[:：]?\s*)?({number_pattern})', answer, re.IGNORECASE)
                if context_matches and len(context_matches) >= 2:
                    for cm in context_matches:
                        try:
                            val = float(re.sub(r'[^\d.]', '', cm[1]))
                            label = cm[0].strip()
                            # 清理标签：去掉无意义的修饰词
                            label = re.sub(r'^(及|对应|的|为|是|有|共)\s*', '', label)
                            label = label[:30] if len(label) > 30 else label
                            if label and val > 0:
                                rows.append({'name': label, 'value': val})
                        except (ValueError, TypeError):
                            continue
                    if len(rows) >= 2:
                        rows = _filter_outlier_rows(rows)
                        if len(rows) >= 2:
                            return pd.DataFrame(rows)

    return None if not rows else pd.DataFrame(rows)


def _filter_outlier_rows(rows: list[dict]) -> list[dict]:
    """过滤远小于其他数值的离群小值（例如从"3个"中误抓到的"1"），避免
    图表上出现毫无意义的单像素柱和误导性的"1"标签。"""
    if len(rows) < 2:
        return rows
    values = [r['value'] for r in rows]
    max_val = max(values)
    if max_val <= 0:
        return rows
    threshold = max_val * 0.05
    return [r for r in rows if r['value'] >= threshold]


def _is_garbled_key(key: str) -> bool:
    """判断解析到的 key 是否是乱码（Java 对象引用、Python repr、driver 内部类型等），
    避免这些内容被当成图表标签或表格列名展示给用户。"""
    if not key:
        return True
    if re.search(r'[a-zA-Z_][\w.]*@[0-9a-f]{6,8}', key):
        return True
    if re.search(r'\b(?:com|org|net|io|java)\.[a-zA-Z][\w.]*', key):
        return True
    if re.search(r"<class\s+['\"]", key):
        return True
    if re.search(r"^[\[\{]|[\]\}]$", key):
        return True
    # 纯 driver 内部类型名/对象引用（区分于合法列名 orders/users/sales）
    if re.search(r'\b(?:KBObjectField|JDBC|ResultSet)\b', key):
        return True
    if re.search(r'^\d+\s*rows?(?:\s|$)', key, re.IGNORECASE):
        return True
    return False


def clean_sql_local(sql: str) -> str:
    """兼容旧调用：自动剥除 HTML 标签。"""
    return clean_sql(sql, strip_html=True)


def strip_markdown_tables(text: str) -> str:
    """剥离 markdown 表格（含表头分隔线 |---|），避免 LLM 生成的预填充表格
    （如带"待查询结果填充"占位符的表格）与系统真实数据表格重复显示。"""
    if not text:
        return text
    # 匹配以 | 开头的连续多行表格（含对齐分隔行 |---|、|:---:| 等）
    text = re.sub(
        r'(?:^|\n)[ \t]*\|[^\n]*\|(?:[ \t]*\n[ \t]*\|[-:\s|]+\|)?'
        r'(?:[ \t]*\n[ \t]*\|[^\n]*\|)*',
        '\n',
        text,
    )
    # 清理可能残留的多余空行
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# 不可读的"乱码"内容特征：Java 对象引用、Python repr 调试输出、driver 内部类型名
GARBLED_PATTERNS = [
    # Java toString 输出：com.kingbase8.util.KBObjectField@7c0a2f2b
    r'[a-zA-Z_][\w.]*@[0-9a-f]{6,8}',
    # Java/Kotlin 类的全限定名（含包路径）
    r'(?:^|\s)(?:com|org|net|io|java)\.[a-zA-Z][\w.]*(?:\s|$|[,;:|])',
    # Python repr：<class 'list'>、<sqlalchemy...>
    r"<class\s+['\"][\w.]+['\"]>",
    r"<sqlalchemy\.[\w.]+(\.[\w]+)?\s+object",
    # Python 列表/字典 repr：['orders']、{'key': 'value'}
    r"\[\s*'[^']*'\s*\]",
    r"\{\s*'[^']*'\s*:\s*'[^']*'\s*\}",
    # 内部 driver 错误/类型提示
    r"\d+\s*rows?\s*(?:affected|returned)?",
    r"KBObjectField|JDBC|ResultSet",
    # 行内"占位符"型描述
    r"待查询结果填充|查询结果填充|待补充|待填充",
]


def strip_garbled_content(text: str) -> str:
    """剥离 LLM 回答中误带的数据库对象引用、Python repr 调试输出等不可读内容。
    这些通常是 LLM 直接复制 SQL 工具 observation（如 KingbaseES JDBC 返回的
    Java 对象 toString、SQLAlchemy 内部 repr）导致的，需要在渲染前清除。"""
    if not text:
        return text

    # 1. 按行扫描：包含乱码特征词的整行直接删除
    cleaned_lines = []
    for line in text.splitlines():
        if any(re.search(pat, line) for pat in GARBLED_PATTERNS):
            continue
        cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)

    # 2. 清理行内的乱码片段（保留行，去掉乱码）
    for pat in GARBLED_PATTERNS:
        text = re.sub(pat, '', text)

    # 3. 清理可能残留的多余空行
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _convert_value(val):
    """将 SQLAlchemy 返回的原始值转换为 DataFrame 友好的 Python 原生类型。
    处理 datetime/Decimal/bytes/UUID 等特殊类型，避免后续处理时类型不一致。"""
    if val is None:
        return None
    if isinstance(val, datetime.datetime):
        return val.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(val, datetime.date):
        return val.strftime('%Y-%m-%d')
    if isinstance(val, datetime.time):
        return val.strftime('%H:%M:%S')
    if isinstance(val, datetime.timedelta):
        return val.total_seconds()
    if isinstance(val, decimal.Decimal):
        return float(val)
    if isinstance(val, bytes):
        try:
            return val.decode('utf-8')
        except UnicodeDecodeError:
            return val.hex()
    if isinstance(val, (set, frozenset)):
        return list(val)
    return val


def run_sql_query(sql: str) -> pd.DataFrame | None:
    try:
        sql = clean_sql_local(sql)
        ensure_read_only_sql(sql)
        engine = init_engine()
        if engine is None:
            return None
        with engine.connect() as conn:
            raw_result = conn.execute(text(sql))
            cols = list(raw_result.keys())
            raw_rows = raw_result.fetchall()
        converted = [tuple(_convert_value(value) for value in row) for row in raw_rows]
        return pd.DataFrame(converted, columns=cols)
    except Exception as exc:
        logger.warning("只读 SQL 执行失败: %s", exc, exc_info=True)
        st.warning(f"查询执行失败：{sanitize_error(exc)}")
        return None


# 节点名 → 进度条文案；执行轨迹面板仍显示英文节点名与耗时明细。
STEP_LABELS = {
    "input_safety": "🔒 输入安全检查",
    "load_history": "📜 加载会话",
    "route": "🔍 解析意图",
    "retrieve": "📚 检索知识",
    "load_schema": "🗂️ 读取表结构",
    "generate_sql": "📝 生成 SQL",
    "validate_sql": "🛡️ 校验 SQL",
    "execute_sql": "🗄️ 执行查询",
    "synthesize": "🤖 合成回答",
    "save_session": "💾 保存会话",
}


def render_live_steps(steps: list[dict]) -> str:
    """把 runtime.astream 实时产出的节点步骤渲染为进度条（复用 step-indicator 样式）。"""
    parts = ['<div class="step-indicator">']
    for index, step in enumerate(steps):
        label = STEP_LABELS.get(step.get("name", ""), step.get("name", "步骤"))
        if step.get("status") == "error":
            # 错误步骤红色高亮并加 ⚠️ 前缀
            label = f"⚠️ {label}"
            css_class = "step-error"
        else:
            # 最后一项视为"当前步骤"高亮，其余标记已完成。
            css_class = "step-active" if index == len(steps) - 1 else "step-done"
        parts.append(f'<span class="step-item {css_class}">{label}</span>')
    parts.append('</div>')
    return ''.join(parts)


def render_sql_block(sql: str, query_time: float | None = None):
    escaped_sql = sql.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    copy_id = f"sql_{hashlib.md5(sql.encode()).hexdigest()[:8]}"
    time_str = f'<div class="query-time">查询耗时：{query_time:.2f} 秒</div>' if query_time else ''

    st.markdown(f"""
    <div class="sql-block">
        <button class="sql-copy-btn" onclick="
            navigator.clipboard.writeText(document.getElementById('{copy_id}').textContent);
            this.textContent='已复制'; setTimeout(()=>this.textContent='复制 SQL', 1500);
        ">复制 SQL</button>
        <pre id="{copy_id}" style="margin:0;white-space:pre-wrap;word-break:break-all;color:#A5B4FC;">{escaped_sql}</pre>
    </div>
    {time_str}
    """, unsafe_allow_html=True)


def render_answer_with_highlights(answer: str):
    # 1. 剥离 LLM 回答中的乱码内容（Java 对象引用、Python repr 调试输出等）
    answer = strip_garbled_content(answer)

    # 2. 剥离 LLM 生成的预填充 markdown 表格（避免与系统真实数据表格重复显示）
    answer = strip_markdown_tables(answer)
    answer = html.escape(answer)

    # 3. 保护 markdown 代码块（```...```），避免数字高亮污染 SQL/代码
    # 注意：占位符不能包含数字或百分号，否则会被下面的高亮正则误匹配
    placeholders: dict[str, str] = {}
    _idx = 0

    def _protect(match):
        nonlocal _idx
        # 26 进制字母编码 (A, B, ..., Z, AA, AB, ...) 避免数字
        n, chars = _idx, []
        _idx += 1
        while True:
            chars.append(chr(ord('A') + n % 26))
            n = n // 26 - 1
            if n < 0:
                break
        idx_str = ''.join(reversed(chars))
        key = f"\x00CODEBLOCKSLOT{idx_str}ENDSLOT\x00"
        placeholders[key] = match.group(0)
        return key

    answer = re.sub(r'```[\s\S]*?```', _protect, answer)

    # 4. 对非代码部分应用高亮
    answer = re.sub(r'(\d+\.?\d*%?)', r'<span class="highlight-num">\1</span>', answer)
    answer = re.sub(r'【[^】]{0,4}异常预警】(.*?)(?=\n|$)', r'<div class="warning-box">异常预警\1</div>', answer)

    # 5. 还原代码块
    for key, original in placeholders.items():
        answer = answer.replace(key, original)

    st.markdown(answer, unsafe_allow_html=True)


def render_agent_steps(steps: list[dict]) -> None:
    if not steps:
        return
    with st.expander(f"执行轨迹 ({len(steps)} 步)", expanded=False):
        for step in steps:
            status = "DONE" if step.get("status") == "success" else "WARN"
            st.caption(
                f"{status} · {step.get('name', 'step')} · {step.get('duration_ms', 0)}ms — "
                f"{step.get('summary', '')}"
            )


db_engine = init_engine()
# RAG 检索器用懒加载代理替代 eager 调用：模块顶层 import 时不拉起
# BGE(93MB) 与 Chromadb，只有当用户真的问出 knowledge/hybrid 类问题时
# 才会触发首次初始化。首页/纯 data 问题路径零 RAG 代价。
retriever = _LazyRetriever()
rag_status = retriever.status  # 初值：未初始化
runtime = get_session_runtime(db_engine, retriever)
render_runtime_status(db_engine, rag_status)
render_setup_guide(db_engine)

with st.sidebar:
    with st.expander("模型连接", expanded=not bool(st.session_state.model_api_key)):
        with st.form("model_connection_form"):
            model_base_url = st.text_input(
                "API Base URL",
                value=st.session_state.model_base_url,
                placeholder="https://api.deepseek.com",
            )
            model_name = st.text_input(
                "模型名称",
                value=st.session_state.model_name,
                placeholder="deepseek-chat",
            )
            model_api_key = st.text_input(
                "API Key",
                value=st.session_state.model_api_key,
                type="password",
                help="仅保存在当前浏览器会话，不写入文件或日志。",
            )
            apply_config = st.form_submit_button("应用配置", use_container_width=True)
            test_connection = st.form_submit_button("测试连接", use_container_width=True)
            if apply_config or test_connection:
                st.session_state.model_base_url = model_base_url.strip()
                st.session_state.model_name = model_name.strip()
                st.session_state.model_api_key = model_api_key.strip()
                st.session_state.pop("runtime_instance", None)
                st.session_state.pop("runtime_fingerprint", None)
            if test_connection:
                if not model_api_key.strip():
                    st.warning("请先填写 API Key")
                else:
                    try:
                        probe = OpenAIModelAdapter(
                            api_key=model_api_key.strip(),
                            base_url=model_base_url.strip(),
                            model=model_name.strip(),
                            business_context=BUSINESS_CONTEXT,
                        )
                        probe.test_connection()
                        st.success("连接成功，模型已响应")
                    except Exception as exc:
                        st.error(f"连接失败：{sanitize_error(exc)}")
            if apply_config:
                st.rerun()

        if st.session_state.model_api_key:
            st.success("模型凭据已在当前会话中配置")
        else:
            st.info("配置兼容 OpenAI API 的模型后即可开始查询")

    st.divider()
    with st.expander("RAG 知识库", expanded=False):
        rag_count = int(rag_status.get("count") or 0)
        if rag_status.get("ok") and rag_count > 0:
            st.success("RAG 已启用")
            st.metric("向量库", f"{rag_count} chunks", label_visibility="visible")
            if retriever:
                stats = retriever.get_stats()
                k1, k2 = st.columns(2)
                k1.metric("命中率", f"{stats['hit_rate_pct']:.0f}%")
                k2.metric("平均延迟", f"{stats['avg_latency_ms']:.0f}ms")
                st.caption(f"缓存: {stats['cache_size']} 条")
        elif rag_status.get("ok"):
            st.warning("RAG 知识库为空")
            st.caption("将降级为纯 SQL 查询模式；请先构建或检查向量库。")
        else:
            st.error(f"RAG 未启用：{rag_status.get('error', '未知错误')[:80]}")
            st.caption("将降级为纯 SQL 查询模式")

    st.header("查询历史")
    if st.session_state.query_history:
        for i, item in enumerate(reversed(st.session_state.query_history[-5:])):
            display_q = item["question"][:25] + "..." if len(item["question"]) > 25 else item["question"]
            if st.button(display_q, key=f"hist_{i}", use_container_width=True):
                st.session_state.pending_question = item["question"]
    else:
        st.caption("暂无查询历史")

    st.divider()
    st.header("示例问题")

    st.markdown("**销售分析**")
    sales_examples = [
        "销售额最高的 3 个商品编号和金额",
        "APP 和微信公众号，谁的订单量更多？",
    ]
    for ex in sales_examples:
        if st.button(ex, key=ex, use_container_width=True):
            st.session_state.pending_question = ex

    st.markdown("**时间分析**")
    time_examples = [
        "最近 7 天每天的销售额是多少？",
        "哪个时间段的订单量最多？",
    ]
    for ex in time_examples:
        if st.button(ex, key=ex, use_container_width=True):
            st.session_state.pending_question = ex

    st.markdown("**用户分析**")
    user_examples = [
        "用户平均消费频次是多少？",
        "各平台的退款率分别是多少？",
    ]
    for ex in user_examples:
        if st.button(ex, key=ex, use_container_width=True):
            st.session_state.pending_question = ex

    st.divider()
    if st.button("清空对话", use_container_width=True):
        st.session_state.messages = [
            {"role": "assistant", "content": "对话已清空，继续提问吧！",
             "chart_data": None, "chart_title": "", "csv_data": None, "sql": None, "query_time": None,
             "rag_sources": []}
        ]
        st.session_state.query_cache = {}
        st.rerun()

    st.divider()
    st.header("智能推荐")
    
    RECOMMENDATIONS = {
        '退款': ['哪个平台退款金额最多？', '退款率最高的时间段是？', '哪些商品退款最多？'],
        '销售': ['各平台销售额占比', '最近7天销售额趋势', 'TOP10热销商品'],
        '订单': ['哪个时间段订单量最多？', 'APP和微信订单量对比', '日均订单量是多少'],
        '用户': ['用户复购率是多少？', '客单价分布情况', '高价值用户特征'],
        '平台': ['各平台的转化率对比', '哪个渠道用户增长最快？', '平台留存率分析'],
        '商品': ['销量最高的TOP5商品', '库存周转快的商品', '新品表现如何'],
        '时间': ['周末和工作日订单对比', '节假日销售高峰', '月度销售趋势'],
    }
    
    last_questions = [h.get("question", "") for h in st.session_state.query_history[-3:]]
    recommended = set()
    
    for q in last_questions:
        for keyword, recs in RECOMMENDATIONS.items():
            if keyword in q:
                for rec in recs[:2]:
                    if rec not in [h.get("question", "") for h in st.session_state.query_history]:
                        recommended.add(rec)
    
    if recommended:
        for rec in list(recommended)[:3]:
            if st.button(rec, key=f"rec_{rec[:20]}", use_container_width=True):
                st.session_state.pending_question = rec
    else:
        st.caption("查询后显示相关推荐")

    st.divider()
    db_type = "MySQL" if USE_MYSQL else "SQLite"
    db_label = "MySQL (ai_commerce_intelligence_platform)" if USE_MYSQL else "SQLite (本地)"
    st.caption(f"数据库：{db_label}")
    st.caption(f"模型：{st.session_state.model_name}")

for msg_idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant" and msg.get("question"):
            col1, col2, col3 = st.columns([1, 1, 3])
            with col1:
                thumbs_up = st.button("有帮助", key=f"up_{msg_idx}")
            with col2:
                thumbs_down = st.button("需改进", key=f"down_{msg_idx}")
            feedback_key = f"fb_{msg_idx}"
            if "feedbacks" not in st.session_state:
                st.session_state.feedbacks = {}
            # 落盘：仅在本次按钮被点击时记录（避免重复触发）
            if thumbs_up:
                st.session_state.feedbacks[feedback_key] = "有帮助"
                record_feedback(
                    question=msg["question"],
                    answer=msg.get("content", ""),
                    rating="up",
                    rag_sources=msg.get("rag_sources", []),
                )
                st.success("感谢反馈！")
            elif thumbs_down:
                st.session_state.feedbacks[feedback_key] = "需改进"
                record_feedback(
                    question=msg["question"],
                    answer=msg.get("content", ""),
                    rating="down",
                    rag_sources=msg.get("rag_sources", []),
                )
                st.info("我们会持续优化，谢谢反馈！")

            # 按钮点击会触发整页重跑；根据已保存的反馈状态持续显示重新生成入口。
            if st.session_state.feedbacks.get(feedback_key) == "需改进":
                if st.button("重新生成", key=f"regen_{msg_idx}", use_container_width=True):
                    st.session_state.pending_question = msg["question"]
                    # 替换这一轮问答，避免重新生成后在对话记录中出现重复内容。
                    if msg_idx > 0 and st.session_state.messages[msg_idx - 1].get("role") == "user":
                        del st.session_state.messages[msg_idx - 1:msg_idx + 1]
                    else:
                        st.session_state.messages.pop(msg_idx)
                    st.rerun()

        
        render_answer_with_highlights(msg["content"])

        # 显示本次回答引用的业务知识（参考来源）
        if msg.get("rag_sources"):
            with st.expander(f"参考知识 ({len(msg['rag_sources'])} 条)", expanded=False):
                for src in msg["rag_sources"]:
                    st.markdown(
                        f"**[{src['rank']}] {src['filename']}** > {src['section']} "
                        f"`相关度 {src['score']:.2f}`"
                    )
                    st.caption(src["preview"])
        render_agent_steps(msg.get("agent_steps") or [])

        if msg.get("csv_data"):
            try:
                csv_df = pd.DataFrame(msg["csv_data"])
                st.dataframe(csv_df, use_container_width=True, hide_index=True)
                st.download_button(
                    "导出 CSV",
                    csv_df.to_csv(index=False).encode("utf-8-sig"),
                    file_name="query_result.csv",
                    mime="text/csv",
                    key=f"dl_{hashlib.md5(str(msg['content'][:80]).encode()).hexdigest()}",
                )
            except Exception:
                pass
        if msg.get("chart_data"):
            try:
                chart_df = pd.DataFrame(msg["chart_data"])
                if len(chart_df) > 0 and len(chart_df.columns) >= 2:
                    fig = create_chart(chart_df, msg.get("chart_title", ""), msg.get("question", ""))
                    if fig:
                        st.plotly_chart(fig, width='stretch', key=f"msg_chart_{msg_idx}", config={
                            'displaylogo': False,
                            'modeBarButtonsToAdd': ['downloadPNG', 'zoomIn', 'zoomOut', 'fullscreen'],
                        })
            except Exception as e:
                st.caption(f"图表加载失败：{str(e)[:50]}")
        if msg.get("sql"):
            render_sql_block(msg["sql"], msg.get("query_time"))

prompt = st.chat_input("输入你的业务问题...")

if hasattr(st.session_state, "pending_question"):
    prompt = st.session_state.pending_question
    del st.session_state.pending_question

if prompt:
    if not runtime:
        recovery = (
            "数据库连接不可用。请先恢复数据库服务或环境变量，再重新提交问题。"
            if db_engine is None
            else "模型 API Key 尚未配置。请在侧栏完成模型连接并测试通过后，再重新提交问题。"
        )
        st.session_state.messages.append({"role": "user", "content": prompt,
                                          "chart_data": None, "chart_title": "", "csv_data": None,
                                          "sql": None, "query_time": None})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            st.warning(recovery)
            st.caption("恢复路径：检查 Base URL、模型名称、API Key 与数据库只读连接；RAG 失败时会自动降级为纯 SQL 查询模式。")
        st.session_state.messages.append({"role": "assistant", "content": recovery,
                                          "chart_data": None, "chart_title": "", "csv_data": None,
                                          "sql": None, "query_time": None, "rag_sources": []})
        st.stop()

    if is_sensitive_query(prompt):
        st.session_state.messages.append({"role": "user", "content": prompt,
                                          "chart_data": None, "chart_title": "", "csv_data": None,
                                          "sql": None, "query_time": None})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            st.warning(SENSITIVE_RESPONSE)
        st.session_state.messages.append({"role": "assistant", "content": SENSITIVE_RESPONSE,
                                          "chart_data": None, "chart_title": "", "csv_data": None,
                                          "sql": None, "query_time": None})
        st.stop()

    cache_key = get_cache_key(prompt)
    if cache_key in st.session_state.query_cache:
        cached = st.session_state.query_cache[cache_key]
        st.session_state.messages.append({"role": "user", "content": prompt,
                                          "chart_data": None, "chart_title": "", "csv_data": None,
                                          "sql": None, "query_time": None})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            st.info("从缓存读取")
            render_answer_with_highlights(cached["answer"])
            if cached.get("csv_data"):
                try:
                    csv_df = pd.DataFrame(cached["csv_data"])
                    st.dataframe(csv_df, use_container_width=True, hide_index=True)
                except Exception:
                    pass
            if cached.get("chart_data"):
                try:
                    chart_df = pd.DataFrame(cached["chart_data"])
                    if len(chart_df) > 0 and len(chart_df.columns) >= 2:
                        fig = create_chart(chart_df, cached.get("chart_title", ""), prompt)
                        if fig:
                            st.plotly_chart(fig, width='stretch', key=f"cache_chart_{cache_key}", config={
                                'displaylogo': False,
                                'modeBarButtonsToAdd': ['downloadPNG', 'zoomIn', 'zoomOut', 'fullscreen'],
                            })
                except Exception as e:
                    st.caption(f"缓存图表加载失败：{str(e)[:50]}")
            if cached.get("csv_data"):
                try:
                    csv_df = pd.DataFrame(cached["csv_data"])
                    st.download_button(
                        "导出 CSV",
                        csv_df.to_csv(index=False).encode("utf-8-sig"),
                        file_name="query_result.csv",
                        mime="text/csv",
                        key=f"cached_dl_{cache_key}",
                    )
                except Exception:
                    pass
            if cached.get("sql"):
                render_sql_block(cached["sql"], cached.get("query_time"))
            render_agent_steps(cached.get("agent_steps") or [])
        st.session_state.messages.append({
            "role": "assistant",
            "content": cached["answer"],
            "chart_data": cached.get("chart_data"),
            "chart_title": cached.get("chart_title"),
            "csv_data": cached.get("csv_data"),
            "sql": cached.get("sql"),
            "query_time": cached.get("query_time"),
            "question": prompt,
            "rag_sources": cached.get("rag_sources") or [],
            "agent_steps": cached.get("agent_steps") or [],
        })
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt,
                                      "chart_data": None, "chart_title": "", "csv_data": None,
                                      "sql": None, "query_time": None})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        step_placeholder = st.empty()
        answer_placeholder = st.empty()
        live_steps: list[dict] = []
        answer_text: list[str] = []

        def _on_step(step: dict) -> None:
            # 节点完成即刷新实时进度；回调与 Streamlit 脚本同线程，可直接更新 UI。
            live_steps.append(step)
            step_placeholder.markdown(render_live_steps(live_steps), unsafe_allow_html=True)

        def _on_token(delta: str) -> None:
            # 答案逐 token 打字机渲染
            answer_text.append(delta)
            answer_placeholder.markdown("".join(answer_text) + "▌")

        try:
            state = asyncio.run(
                runtime.astream(
                    prompt,
                    owner="streamlit-session",
                    thread_id=st.session_state.thread_id,
                    on_step=_on_step,
                    on_token=_on_token,
                )
            )
            agent_result = state["result"]
            answer = agent_result.answer
            query_time = agent_result.usage.latency_ms / 1000 if agent_result.usage else None
            rag_sources = [
                {
                    "rank": index,
                    "filename": source.filename,
                    "section": source.section,
                    "doc_type": source.doc_type,
                    "score": source.score,
                    "preview": source.snippet,
                }
                for index, source in enumerate(agent_result.sources, 1)
            ]
            agent_steps = [
                {
                    "name": step.name,
                    "status": step.status,
                    "duration_ms": step.duration_ms,
                    "summary": step.summary,
                }
                for step in agent_result.steps
            ]
        except Exception as exc:
            step_placeholder.empty()
            answer_placeholder.empty()
            st.error(f"执行出错：{sanitize_error(exc)}")
            st.session_state.messages.append({
                "role": "assistant",
                "content": "执行失败。请检查模型 Base URL、API Key、模型名称与数据库只读连接后重试；你的问题已保留在对话中。",
                "chart_data": None, "chart_title": "", "csv_data": None,
                "sql": None, "query_time": None, "rag_sources": [],
            })
            st.stop()

        # 流式渲染结束：清空占位（含打字机光标），改用高亮版最终答案。
        step_placeholder.empty()
        answer_placeholder.empty()

        chart_data = None
        chart_title = prompt[:30]
        csv_data = None
        extracted_sql = agent_result.sql

        render_answer_with_highlights(answer)
        render_agent_steps(agent_steps)
        result_df = pd.DataFrame(agent_result.rows)


        if result_df is None or (isinstance(result_df, pd.DataFrame) and len(result_df) == 0):
            result_df = parse_data_from_answer(answer)
            if result_df is not None and len(result_df) > 0:
                st.info(f"从回答文本解析数据成功，行数：{len(result_df)}")
        
        if result_df is not None and len(result_df) > 0:
            st.dataframe(result_df, use_container_width=True, hide_index=True)
            chart_data = result_df.to_dict(orient="records")
            csv_data = result_df.to_dict(orient="records")

            is_single_value = len(result_df) == 1 and len(result_df.columns) == 1
            is_avg_question = any(k in prompt.lower() or k in prompt for k in ['平均', 'avg', 'mean', 'per capita'])
            
            if is_single_value or (is_avg_question and len(result_df) == 1):
                if is_avg_question and len(result_df.columns) > 1:
                    avg_cols = [c for c in result_df.columns if 'avg' in c.lower() or 'freq' in c.lower() or 'per' in c.lower()]
                    if avg_cols:
                        target_col = avg_cols[0]
                    else:
                        target_col = result_df.columns[-1]
                else:
                    target_col = result_df.columns[0]
                
                single_val = result_df.iloc[0][target_col]
                st.metric(label="查询结果", value=f"{single_val:.2f}" if isinstance(single_val, (int, float)) else str(single_val))
                chart_data = None
            else:
                fig = create_chart(result_df, chart_title, prompt)
                if fig:
                    st.plotly_chart(fig, width='stretch', key=f"live_chart_{cache_key}", config={
                        'displaylogo': False,
                        'modeBarButtonsToAdd': ['downloadPNG', 'zoomIn', 'zoomOut', 'fullscreen'],
                    })
            
            st.download_button(
                "导出 CSV",
                result_df.to_csv(index=False).encode("utf-8-sig"),
                file_name="query_result.csv",
                mime="text/csv",
                key=f"dl_{cache_key}",
            )
        
        elif extracted_sql:
            st.warning("SQL 执行无结果")

        if extracted_sql:
            render_sql_block(extracted_sql, query_time)

        msg_data = {
            "role": "assistant",
            "content": answer,
            "chart_data": chart_data,
            "chart_title": chart_title,
            "csv_data": csv_data,
            "sql": extracted_sql,
            "query_time": query_time,
            "question": prompt,
            "rag_sources": rag_sources,
            "agent_steps": agent_steps,
        }
        st.session_state.messages.append(msg_data)

        st.session_state.query_cache[cache_key] = {
            "answer": answer,
            "chart_data": chart_data,
            "chart_title": chart_title,
            "csv_data": csv_data,
            "sql": extracted_sql,
            "query_time": query_time,
            "rag_sources": rag_sources,
            "agent_steps": agent_steps,
        }

        st.session_state.query_history.append({
            "question": prompt,
            "answer": answer[:100],
        })
