"""基于SQL AST的只读校验与结果行数限制。"""

from __future__ import annotations

from sqlglot import exp, parse, parse_one
from sqlglot.errors import ParseError

# MySQL 优化器提示：由数据库自己在超时后中断查询（5.7.8+ / 8.0 支持）。
_MYSQL_TIMEOUT_HINT = "MAX_EXECUTION_TIME"


class SQLValidationError(ValueError):
    pass


def validate_and_limit_sql(
    sql: str,
    max_rows: int = 500,
    allowed_tables: tuple[str, ...] = ("orders",),
    max_joins: int = 3,
) -> str:
    """校验只读性并改写 LIMIT；JOIN 数量超限一律拒绝。

    max_joins 不只是"复杂度"限制：模型可能生成多表笛卡尔积，而 LIMIT 只裁剪
    最终输出行数，中间结果仍然要被完整算完，因此必须在 AST 层提前拦掉。
    """
    try:
        statements = parse(sql, read="mysql")
    except ParseError as exc:
        raise SQLValidationError("SQL语法无法解析") from exc
    if len(statements) != 1 or not isinstance(statements[0], exp.Query):
        raise SQLValidationError("仅允许单条SELECT/WITH查询")

    expression = statements[0]
    forbidden = (exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop, exp.Alter, exp.Merge, exp.Lock)
    if any(expression.find(node_type) is not None for node_type in forbidden):
        raise SQLValidationError("查询包含写入或结构变更操作")

    dangerous_functions = {"sleep", "benchmark", "load_file"}
    if any(
        isinstance(node, exp.Anonymous) and node.name.lower() in dangerous_functions
        for node in expression.walk()
    ):
        raise SQLValidationError("查询包含不允许的数据库函数")

    join_count = sum(1 for node in expression.walk() if isinstance(node, exp.Join))
    if join_count > max_joins:
        raise SQLValidationError(f"查询包含 {join_count} 个 JOIN，超出 {max_joins} 个上限")

    cte_names = {cte.alias_or_name.lower() for cte in expression.find_all(exp.CTE)}
    table_names = {table.name.lower() for table in expression.find_all(exp.Table)} - cte_names
    if table_names - {name.lower() for name in allowed_tables}:
        raise SQLValidationError("查询访问了未授权的数据表")

    limit = expression.args.get("limit")
    if limit is None:
        expression = expression.limit(max_rows)
    else:
        value = limit.expression
        if isinstance(value, exp.Literal) and value.is_int and int(value.this) > max_rows:
            expression.set("limit", exp.Limit(expression=exp.Literal.number(max_rows)))
    return expression.sql(dialect="mysql")


def apply_execution_guard(sql: str, timeout_ms: int, dialect: str = "mysql") -> str:
    """把执行时限下推到数据库，返回改写后的 SQL。

    asyncio.wait_for 只能取消协程，无法中断已经在数据库内运行的查询：超时后
    API 已经返回"查询执行超时"，但慢查询仍在库上继续跑，连接也一直被占用，
    因此真正的上限必须由数据库自己执行。

    MySQL 用 MAX_EXECUTION_TIME 优化器提示（仅对 SELECT 生效）；
    SQLite / 其他方言没有等价语法，保持原样并依赖上层等待作为兜底。
    """
    if timeout_ms <= 0 or dialect != "mysql":
        return sql
    try:
        expression = parse_one(sql, read=dialect)
    except ParseError:
        return sql
    # MySQL 要求 hint 位于整条语句的第一个 SELECT 后；UNION 根节点本身
    # 不能挂 hint，因此定位左侧第一个 SELECT，使时限覆盖整条 UNION。
    target = expression if isinstance(expression, exp.Select) else next(expression.find_all(exp.Select), None)
    if target is None:
        return sql
    target.set(
        "hint",
        exp.Hint(
            expressions=[
                exp.Anonymous(this=_MYSQL_TIMEOUT_HINT, expressions=[exp.Literal.number(timeout_ms)])
            ]
        ),
    )
    return expression.sql(dialect=dialect)


def dialect_from_url(url: str) -> str:
    """从 SQLAlchemy 连接串提取方言名，如 mysql+pymysql://... -> mysql。"""
    return url.split("://", 1)[0].split("+", 1)[0].strip().lower()
