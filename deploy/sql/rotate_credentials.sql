-- 密钥轮换脚本模板：执行前请先按 .env 实际值替换 <NEW_DB_PASSWORD>
-- 用法：
--   1. 用 secrets 生成新密码（16 位字母数字，避免特殊字符转义问题）
--   2. 同步更新 backend/.env 与根 .env 的 DB_PASSWORD
--   3. 将下方 <NEW_DB_PASSWORD> 替换后执行
-- 提示：含真实密码的本地副本见 rotate_credentials.local.sql（已 gitignore）
-- 使用 CREATE USER IF NOT EXISTS + ALTER USER：全新库 / 已部署库均可安全执行

-- Root 密码（仅本地开发环境；生产环境应通过 mysql_secure_installation 单独管理）
ALTER USER 'root'@'localhost' IDENTIFIED BY '<NEW_DB_PASSWORD>';
CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY '<NEW_DB_PASSWORD>';
ALTER USER 'root'@'%' IDENTIFIED BY '<NEW_DB_PASSWORD>';

-- 业务账号密码（与 bootstrap-users.sh 中的变量保持一致）
CREATE USER IF NOT EXISTS 'ea_app'@'%' IDENTIFIED BY '<NEW_DB_PASSWORD>';
ALTER USER 'ea_app'@'%' IDENTIFIED BY '<NEW_DB_PASSWORD>';
GRANT SELECT ON `ai_commerce_intelligence_platform`.* TO 'ea_app'@'%';

CREATE USER IF NOT EXISTS 'ea_ai'@'%' IDENTIFIED BY '<NEW_DB_PASSWORD>';
ALTER USER 'ea_ai'@'%' IDENTIFIED BY '<NEW_DB_PASSWORD>';
GRANT SELECT ON `ai_commerce_intelligence_platform`.* TO 'ea_ai'@'%';

CREATE USER IF NOT EXISTS 'ea_sync'@'%' IDENTIFIED BY '<NEW_DB_PASSWORD>';
ALTER USER 'ea_sync'@'%' IDENTIFIED BY '<NEW_DB_PASSWORD>';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, INDEX
  ON `ai_commerce_intelligence_platform`.* TO 'ea_sync'@'%';
GRANT FILE ON *.* TO 'ea_sync'@'%';

FLUSH PRIVILEGES;