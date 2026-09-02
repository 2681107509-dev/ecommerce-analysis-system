"""流式上下文：把答案 token 从注入式回调转发给调用方。

设计约束：
- AgentRuntime 的回调（answer_generator 等）由调用端注入，签名固定；
  这里用 ContextVar 在同一次 astream() 执行期内传递 token 钩子，
  既不破坏既有协议，也天然支持并发（asyncio 任务各自持有上下文副本）。
"""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar

TokenHook = Callable[[str], None]

_token_hook: ContextVar[TokenHook | None] = ContextVar("agent_core_token_hook", default=None)


def set_token_hook(hook: TokenHook | None):
    """绑定当前任务上下文的 token 钩子；返回用于恢复的 token。"""
    return _token_hook.set(hook)


def reset_token_hook(token) -> None:
    """恢复到 set_token_hook 之前的状态，避免钩子泄漏到后续调用。"""
    _token_hook.reset(token)


def emit_token(delta: str) -> None:
    """answer 生成方调用：有监听者时转发增量，否则静默丢弃。"""
    hook = _token_hook.get()
    if hook is not None and delta:
        hook(delta)
