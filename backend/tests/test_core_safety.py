from inspect import Signature, signature
from types import SimpleNamespace

import pytest

from backend.models.schemas import SalesOverviewResponse
from backend.services.rfm_service import _score_users
from backend.utils import cache
from backend.utils.rate_limiter import _get_client_id
from backend.utils.sql_guard import is_read_only_sql


@pytest.mark.parametrize("sql", [
    "SELECT 1",
    "WITH totals AS (SELECT 1 AS n) SELECT n FROM totals",
    "SHOW TABLES",
    "DESCRIBE orders",
    "SELECT ';' AS value",
    "SELECT '-- not a comment' AS value",
])
def test_read_only_sql_accepts_queries(sql):
    assert is_read_only_sql(sql)


@pytest.mark.parametrize("sql", [
    "DELETE\nFROM orders",
    "WITH x AS (SELECT 1) DELETE FROM orders",
    "SELECT * FROM orders INTO OUTFILE '/tmp/orders.csv'",
    "CALL dangerous_proc()",
    "SET @x = 1",
    "SELECT 1; DROP TABLE orders",
    "SELECT '--'; DROP TABLE orders",
    "SELECT '/*'; DELETE FROM orders",
    "SELECT SLEEP(10)",
])
def test_read_only_sql_blocks_mutation_and_side_effects(sql):
    assert not is_read_only_sql(sql)


def test_rfm_recent_user_gets_lower_r_score():
    users = [
        {"user_name": "recent", "recency_days": 1, "frequency": 3, "monetary": 3000},
        {"user_name": "middle", "recency_days": 30, "frequency": 2, "monetary": 1000},
        {"user_name": "old", "recency_days": 180, "frequency": 1, "monetary": 100},
    ]
    scored = _score_users(users, n_bins=3)
    by_name = {u["user_name"]: u for u in scored}
    assert by_name["recent"]["r_score"] < by_name["old"]["r_score"]
    assert by_name["recent"]["segment"].startswith("重要")
    assert by_name["old"]["segment"].startswith("一般")


class _FakeRedis:
    def __init__(self):
        self.data = {}

    def setex(self, key, _ttl, value):
        self.data[key] = value

    def get(self, key):
        return self.data.get(key)


@pytest.mark.asyncio
async def test_cached_pydantic_model_round_trips_through_redis(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(cache, "_redis_client", fake)
    monkeypatch.setattr(cache, "_redis_available", True)

    calls = 0

    @cache.cached(ttl=60)
    async def get_overview() -> SalesOverviewResponse:
        nonlocal calls
        calls += 1
        return SalesOverviewResponse(
            total_sales=100,
            total_orders=2,
            avg_order_value=50,
            total_users=2,
            refund_rate=0,
            total_refund_amount=0,
        )

    first = await get_overview()
    second = await get_overview()

    assert calls == 1
    assert isinstance(first, SalesOverviewResponse)
    assert isinstance(second, SalesOverviewResponse)
    assert second.total_sales == 100


@pytest.mark.asyncio
async def test_cached_function_without_return_annotation(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(cache, "_redis_client", fake)
    monkeypatch.setattr(cache, "_redis_available", True)

    calls = 0

    @cache.cached(ttl=60)
    async def get_data():
        nonlocal calls
        calls += 1
        return {"ok": True}

    assert signature(get_data).return_annotation is Signature.empty
    assert await get_data() == {"ok": True}
    assert await get_data() == {"ok": True}
    assert calls == 1


def test_proxy_headers_are_ignored_by_default():
    request = SimpleNamespace(
        headers={"x-real-ip": "203.0.113.9"},
        client=SimpleNamespace(host="127.0.0.1"),
    )
    assert _get_client_id(request) == "127.0.0.1"
    assert _get_client_id(request, trust_proxy_headers=True) == "203.0.113.9"
