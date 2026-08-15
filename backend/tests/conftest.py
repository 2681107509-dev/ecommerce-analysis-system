"""pytest 共享 fixture。"""
from __future__ import annotations

import asyncio
import os
import sys

import pytest


def pytest_configure(config):
    """Windows 使用 Selector loop，避免 aiomysql 测试连接跨事件循环失效。"""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # 测试环境与生产 .env 解耦：生产 .env 已轮换为 bcrypt 哈希 + DEBUG=False，
    # 而集成测试钉死 admin/admin123（与 CI workflow 写 .env 的行为一致）。
    # 环境变量优先级高于 .env 文件；仅在未显式设置时兜底，不覆盖 CI 传参。
    os.environ.setdefault("DEBUG", "true")
    os.environ.setdefault("ADMIN_PASSWORD", "admin123")
    os.environ.setdefault("ANALYST_PASSWORD", "analyst123")


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """每个测试前后清空限流计数。

    登录接口默认有限流；测试间共享计数会导致后续 fixture 意外收到 429。
    """
    from backend.utils import rate_limiter
    rate_limiter._rate_store.clear()
    yield
    rate_limiter._rate_store.clear()
