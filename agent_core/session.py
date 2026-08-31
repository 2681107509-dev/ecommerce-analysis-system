"""按用户隔离、带TTL和容量上限的多轮会话存储。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections import OrderedDict
from typing import Protocol

Message = dict[str, str]


class ConversationStore(Protocol):
    async def get_history(self, owner: str, thread_id: str) -> list[Message]: ...
    async def save_turn(self, owner: str, thread_id: str, question: str, answer: str) -> None: ...


class MemoryConversationStore:
    def __init__(self, ttl_seconds: int = 1800, max_sessions: int = 1000, max_turns: int = 6):
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions
        self.max_messages = max_turns * 2
        self._items: OrderedDict[str, tuple[float, list[Message]]] = OrderedDict()
        self._lock = asyncio.Lock()

    @staticmethod
    def _key(owner: str, thread_id: str) -> str:
        return hashlib.sha256(f"{owner}:{thread_id}".encode()).hexdigest()

    async def get_history(self, owner: str, thread_id: str) -> list[Message]:
        key = self._key(owner, thread_id)
        async with self._lock:
            item = self._items.get(key)
            if item is None:
                return []
            expires_at, messages = item
            if expires_at <= time.monotonic():
                self._items.pop(key, None)
                return []
            self._items.move_to_end(key)
            return [dict(message) for message in messages]

    async def save_turn(self, owner: str, thread_id: str, question: str, answer: str) -> None:
        key = self._key(owner, thread_id)
        async with self._lock:
            current = self._items.get(key, (0.0, []))[1]
            messages = [*current, {"role": "user", "content": question}, {"role": "assistant", "content": answer}]
            self._items[key] = (time.monotonic() + self.ttl_seconds, messages[-self.max_messages:])
            self._items.move_to_end(key)
            while len(self._items) > self.max_sessions:
                self._items.popitem(last=False)


class RedisConversationStore:
    def __init__(self, redis_url: str, ttl_seconds: int = 1800, max_turns: int = 6):
        from redis.asyncio import from_url

        self._redis = from_url(redis_url, decode_responses=True, socket_connect_timeout=2)
        self.ttl_seconds = ttl_seconds
        self.max_messages = max_turns * 2

    @staticmethod
    def _key(owner: str, thread_id: str) -> str:
        digest = hashlib.sha256(f"{owner}:{thread_id}".encode()).hexdigest()
        return f"agent:thread:{digest}"

    async def get_history(self, owner: str, thread_id: str) -> list[Message]:
        payload = await self._redis.get(self._key(owner, thread_id))
        if not payload:
            return []
        value = json.loads(payload)
        return value if isinstance(value, list) else []

    async def save_turn(self, owner: str, thread_id: str, question: str, answer: str) -> None:
        history = await self.get_history(owner, thread_id)
        history.extend(({"role": "user", "content": question}, {"role": "assistant", "content": answer}))
        await self._redis.setex(
            self._key(owner, thread_id),
            self.ttl_seconds,
            json.dumps(history[-self.max_messages:], ensure_ascii=False),
        )


class FallbackConversationStore:
    """Redis异常时自动使用有界内存存储，不影响主查询链路。"""

    def __init__(self, primary: ConversationStore | None, fallback: MemoryConversationStore | None = None):
        self.primary = primary
        self.fallback = fallback or MemoryConversationStore()

    async def get_history(self, owner: str, thread_id: str) -> list[Message]:
        if self.primary is not None:
            try:
                return await self.primary.get_history(owner, thread_id)
            except Exception:
                pass
        return await self.fallback.get_history(owner, thread_id)

    async def save_turn(self, owner: str, thread_id: str, question: str, answer: str) -> None:
        if self.primary is not None:
            try:
                await self.primary.save_turn(owner, thread_id, question, answer)
                return
            except Exception:
                pass
        await self.fallback.save_turn(owner, thread_id, question, answer)
