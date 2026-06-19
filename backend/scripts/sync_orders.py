"""Docker 启动时将主 CSV 幂等同步到 MySQL。

CSV 是平台订单主数据源。仅当文件哈希或行数变化时重建临时表，
校验成功后再原子换表，避免持久化数据卷长期停留在旧版本。
"""
from __future__ import annotations

import csv
import hashlib
import logging
import os
import time
from pathlib import Path

import pymysql

logger = logging.getLogger("sync_orders")

CSV_PATH = Path(os.getenv("ORDERS_CSV_PATH", "/app/data/cleaned_orders.csv"))
IMPORT_SQL_PATH = Path(os.getenv("ORDERS_IMPORT_SQL", "/app/sql/02_import_data.sql"))
SERVER_CSV_PATH = os.getenv(
    "ORDERS_SERVER_CSV_PATH",
    "/var/lib/mysql-files/cleaned_orders.csv",
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_row_count(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.reader(file)
        next(reader, None)
        return sum(1 for _ in reader)


def build_import_sql(sql_template: str, table_name: str) -> str:
    sql = sql_template.replace(
        "INTO TABLE orders",
        f"INTO TABLE {table_name}",
        1,
    )
    return sql.replace(
        "/var/lib/mysql-files/cleaned_orders.csv",
        SERVER_CSV_PATH,
        1,
    )


def connect_with_retry(max_attempts: int = 30):
    # 数据同步需要建临时表和原子换表，使用独立账号，不复用 API 只读账号。
    password = os.getenv("DB_SYNC_PASSWORD", os.getenv("DB_PASSWORD", ""))
    for attempt in range(1, max_attempts + 1):
        try:
            return pymysql.connect(
                host=os.getenv("DB_HOST", "mysql"),
                port=int(os.getenv("DB_PORT", "3306")),
                user=os.getenv(
                    "DB_SYNC_USER",
                    os.getenv("DB_USER", "root"),
                ),
                password=password,
                database=os.getenv(
                    "DB_NAME",
                    "ai_commerce_intelligence_platform",
                ),
                charset="utf8mb4",
                autocommit=True,
            )
        except pymysql.MySQLError:
            if attempt == max_attempts:
                raise
            time.sleep(2)


def sync_orders() -> bool:
    if os.getenv("SYNC_ORDERS_ON_STARTUP", "false").lower() != "true":
        logger.info("订单同步未启用，跳过")
        return False

    csv_hash = file_sha256(CSV_PATH)
    expected_rows = csv_row_count(CSV_PATH)
    import_sql = build_import_sql(
        IMPORT_SQL_PATH.read_text(encoding="utf-8"),
        "orders_staging",
    )

    connection = connect_with_retry()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS app_metadata (
                    meta_key VARCHAR(100) PRIMARY KEY,
                    meta_value VARCHAR(255) NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            cursor.execute(
                "SELECT meta_value FROM app_metadata WHERE meta_key=%s",
                ("orders_csv_sha256",),
            )
            row = cursor.fetchone()
            cursor.execute("SELECT COUNT(*) FROM orders")
            current_rows = cursor.fetchone()[0]

            if row and row[0] == csv_hash and current_rows == expected_rows:
                logger.info("订单数据已是最新版本，共 %s 条", current_rows)
                return False

            logger.info(
                "同步订单数据：数据库 %s 条 → CSV %s 条",
                current_rows,
                expected_rows,
            )
            cursor.execute("DROP TABLE IF EXISTS orders_staging")
            cursor.execute("CREATE TABLE orders_staging LIKE orders")
            cursor.execute(import_sql)
            cursor.execute("SELECT COUNT(*) FROM orders_staging")
            imported_rows = cursor.fetchone()[0]
            if imported_rows != expected_rows:
                cursor.execute("DROP TABLE orders_staging")
                raise RuntimeError(
                    f"订单导入行数不一致: expected={expected_rows}, "
                    f"actual={imported_rows}"
                )

            cursor.execute("DROP TABLE IF EXISTS orders_previous")
            cursor.execute(
                "RENAME TABLE orders TO orders_previous, "
                "orders_staging TO orders"
            )
            cursor.execute("DROP TABLE orders_previous")
            cursor.execute(
                """
                INSERT INTO app_metadata (meta_key, meta_value)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE meta_value=VALUES(meta_value)
                """,
                ("orders_csv_sha256", csv_hash),
            )
            logger.info("订单同步完成，共 %s 条", imported_rows)
            return True
    finally:
        connection.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    sync_orders()
