"""RAG 模块：业务知识检索增强。

子模块：
- embeddings:   Embedding 模型工厂（BGE-small-zh-v1.5）
- vector_store: Chroma 封装
- retriever:    检索器（缓存/超时/统计埋点）
- metrics:      跨进程 stats 共享 + JSONL 事件

检索不再由模型自主触发：agent_core 的确定性工作流按意图调度本模块，
因此这里不再提供 LangChain Tool 工厂与 Agent 侧来源还原。
v1 的 ReAct 工具调用版本已归档，见 README「架构演进」与 git tag archive-react-v1。

构建脚本：见 build_knowledge_base.py
"""
from .embeddings import DEFAULT_MODEL, get_embeddings
from .retriever import Retriever
from .vector_store import DEFAULT_PERSIST_DIR, VectorStore

__all__ = [
    "DEFAULT_MODEL",
    "DEFAULT_PERSIST_DIR",
    "Retriever",
    "VectorStore",
    "get_embeddings",
]
