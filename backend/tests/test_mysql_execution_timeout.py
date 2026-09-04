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
                # 这条失控查询有两个终止路径：MAX_EXECUTION_TIME(100ms) 触发 3024，
                # 或递归撞到深度上限触发 3636。深度设为 1M 时二者耗时接近（约 100ms），
                # 形成竞态——约 1/8 概率先撞 3636，测试就从"验证执行时限生效"
                # 退化成"验证递归深度上限"。抬到 MySQL 最大值 4294967295 后，
                # 递归不可能在 100ms 内耗尽，只剩 3024 一条路径。
                # 另：深度必须在会话级设置，早期用 SET_VAR 提示时同样偶发失效。
                connection.execute(text("SET SESSION cte_max_recursion_depth = 4294967295"))
                connection.execute(text(runaway_cte))

        assert exc_info.value.orig.args[0] == 3024
        assert time.perf_counter() - started < 1.5
        with engine.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        engine.dispose()
