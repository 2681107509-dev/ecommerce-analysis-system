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
        SELECT /*+ MAX_EXECUTION_TIME(100) SET_VAR(cte_max_recursion_depth = 1M) */ * FROM cte
    """

    try:
        with pytest.raises(DBAPIError) as exc_info:
            with engine.connect() as connection:
                connection.execute(text(runaway_cte))

        assert exc_info.value.orig.args[0] == 3024
        assert time.perf_counter() - started < 1.5
        with engine.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        engine.dispose()
