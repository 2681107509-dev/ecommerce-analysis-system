"""MySQL 侧执行时限集成测试；CI 提供真实 MySQL 8 服务。"""

from __future__ import annotations

import time

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from backend.config import get_settings


def test_mysql_max_execution_time_interrupts_query_and_releases_connection() -> None:
    """不能只测 SQL 字符串：必须证明数据库会终止查询且连接池仍可用。"""
    engine = create_engine(
        get_settings().database_url,
        pool_size=1,
        max_overflow=0,
        connect_args={"read_timeout": 2},
    )
    started = time.perf_counter()
    runaway_cte = """
        WITH RECURSIVE cte (n) AS (
            SELECT 1
            UNION ALL
            SELECT n + 1 FROM cte
        )
        SELECT /*+ MAX_EXECUTION_TIME(100) */ * FROM cte
    """

    try:
        with pytest.raises(DBAPIError) as exc_info:
            with engine.connect() as connection:
                # 递归深度必须在会话级抬高：否则查询会先撞上 cte_max_recursion_depth
                # 上限报 3636，轮不到 MAX_EXECUTION_TIME 的 3024 中断，测试就从
                # "验证执行时限生效"退化成"验证递归深度上限"。
                # 早期用 SET_VAR 提示设置该值时偶发失效，曾导致间歇性断言失败。
                connection.execute(text("SET SESSION cte_max_recursion_depth = 1048576"))
                connection.execute(text(runaway_cte))

        assert exc_info.value.orig.args[0] == 3024
        assert time.perf_counter() - started < 1.5
        with engine.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        engine.dispose()
