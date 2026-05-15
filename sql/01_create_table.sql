-- ==========================================
-- 1. 各平台销售额占比（渠道效能分析）
-- 业务意义：判断流量投放重心，收缩低效渠道
-- ==========================================
SELECT 
    platform_type AS '平台类型',
    COUNT(order_id) AS '订单量',
    ROUND(SUM(payment_amount), 2) AS '总销售额',
    ROUND(SUM(payment_amount) / (SELECT SUM(payment_amount) FROM orders) * 100, 2) AS '占比(%)'
FROM orders
GROUP BY platform_type
ORDER BY 总销售额 DESC;
-- ==========================================
-- 2. 爆款商品 TOP10（商品贡献度分析）
-- 业务意义：识别头部商品，指导库存备货与流量倾斜
-- ==========================================
SELECT 
    product_id AS '商品编号',
    COUNT(order_id) AS '被下单次数',
    ROUND(SUM(payment_amount), 2) AS '总销售额'
FROM orders
GROUP BY product_id
ORDER BY 总销售额 DESC
LIMIT 10;
-- ==========================================
-- 3. 每日销售趋势（时间序列分析）
-- 业务意义：观察促销/节假日影响，预测备货节奏
-- ==========================================
SELECT 
    DATE(order_time) AS '销售日期',
    ROUND(SUM(payment_amount), 2) AS '当日销售额',
    COUNT(order_id) AS '当日订单数'
FROM orders
GROUP BY DATE(order_time)
ORDER BY 销售日期 ASC;
-- ==========================================
-- 4. 高价值用户 TOP10（用户分层基础）
-- 业务意义：锁定核心客群，为后续 RFM/会员运营打底
-- ==========================================
SELECT 
    user_name AS '用户名',
    COUNT(order_id) AS '累计订单数',
    ROUND(SUM(payment_amount), 2) AS '累计消费额',
    ROUND(SUM(payment_amount) / COUNT(order_id), 2) AS '客单价'
FROM orders
GROUP BY user_name
ORDER BY 累计消费额 DESC
LIMIT 10;