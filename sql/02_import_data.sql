-- ============================================
-- 02_import_data.sql
-- 导入电商订单数据
-- ============================================

USE ecommerce_analysis;

-- 方法1：LOAD DATA 导入 CSV（推荐，适合大数据量）
-- 注意：需要先确保 MySQL 服务有文件读取权限

LOAD DATA INFILE 'D:/ecommerce_analysis/data/cleaned_orders.csv'
INTO TABLE orders
FIELDS TERMINATED BY ','
ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS
(@dummy, order_seq, order_no, username, product_no,
 order_amount, payment_amount, channel_no, platform_type,
 order_time, payment_time, is_refund, discount_amount,
 pay_duration, order_date, order_hour, weekday)
SET
    order_seq = NULLIF(@dummy, ''),
    order_seq = NULLIF(order_seq, '');

-- 方法2：逐条 INSERT（适合小数据量或测试）
-- INSERT INTO orders (order_seq, order_no, username, product_no, ...)
-- VALUES (8, 'sys-2025-306447069', 'user-104863', 'PR000499', ...);

-- 方法3：使用 mysqlimport 命令行工具
-- mysqlimport --lines-terminated-by='\n' --fields-terminated-by=',' ecommerce_analysis orders.csv

-- 验证数据导入
SELECT COUNT(*) AS total_rows FROM orders;
SELECT '数据导入完成！' AS status;