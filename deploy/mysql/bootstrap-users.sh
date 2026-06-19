#!/bin/sh
set -eu

# 该脚本由一次性 db-bootstrap 容器执行，因此也适用于已经存在的 MySQL 数据卷。
# 应用账号只读；同步账号额外拥有原子换表与 LOAD DATA INFILE 所需权限。

case "${DB_NAME}" in
  *[!A-Za-z0-9_]*|'')
    echo "DB_NAME 只能包含字母、数字和下划线" >&2
    exit 1
    ;;
esac

escape_sql_string() {
  printf '%s' "$1" | sed "s/\\\\/\\\\\\\\/g; s/'/''/g"
}

APP_PASSWORD_ESCAPED="$(escape_sql_string "${DB_APP_PASSWORD}")"
AI_PASSWORD_ESCAPED="$(escape_sql_string "${DB_AI_PASSWORD}")"
SYNC_PASSWORD_ESCAPED="$(escape_sql_string "${DB_SYNC_PASSWORD}")"

mysql --protocol=TCP -h mysql -uroot <<SQL
CREATE USER IF NOT EXISTS 'ea_app'@'%' IDENTIFIED BY '${APP_PASSWORD_ESCAPED}';
ALTER USER 'ea_app'@'%' IDENTIFIED BY '${APP_PASSWORD_ESCAPED}';
GRANT SELECT ON \`${DB_NAME}\`.* TO 'ea_app'@'%';

CREATE USER IF NOT EXISTS 'ea_ai'@'%' IDENTIFIED BY '${AI_PASSWORD_ESCAPED}';
ALTER USER 'ea_ai'@'%' IDENTIFIED BY '${AI_PASSWORD_ESCAPED}';
GRANT SELECT ON \`${DB_NAME}\`.* TO 'ea_ai'@'%';

CREATE USER IF NOT EXISTS 'ea_sync'@'%' IDENTIFIED BY '${SYNC_PASSWORD_ESCAPED}';
ALTER USER 'ea_sync'@'%' IDENTIFIED BY '${SYNC_PASSWORD_ESCAPED}';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, INDEX
  ON \`${DB_NAME}\`.* TO 'ea_sync'@'%';
GRANT FILE ON *.* TO 'ea_sync'@'%';

FLUSH PRIVILEGES;
SQL

echo "数据库最小权限账号已就绪"
