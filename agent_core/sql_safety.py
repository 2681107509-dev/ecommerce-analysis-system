"""基于SQL AST的只读校验与结果行数限制。"""

from __future__ import annotations

from sqlglot import exp, parse
from sqlglot.errors import ParseError


class SQLValidationError(ValueError):
    pass


def validate_and_limit_sql(
    sql: str,
    max_rows: int = 500,
    allowed_tables: tuple[str, ...] = ("orders",),
) -> str:
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
