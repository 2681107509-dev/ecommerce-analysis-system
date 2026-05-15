-- ==========================================
-- 1. 商品销售额排名（展示并列排名逻辑）
-- 业务意义：备货优先级、流量倾斜依据
-- ==========================================
SELECT 
    product_id AS '商品编号',
    SUM(payment_amount) AS '总销售额',
    ROW_NUMBER() OVER(ORDER BY SUM(payment_amount) DESC) AS '强制排名(无并列)',
    RANK() OVER(ORDER BY SUM(payment_amount) DESC) AS '跳跃排名(有并列)',
    DENSE_RANK() OVER(ORDER BY SUM(payment_amount) DESC) AS '连续排名(推荐)'
FROM orders
GROUP BY product_id
ORDER BY 总销售额 DESC
LIMIT 15;
-- ==========================================
-- 2. 每日销售额 & 环比增长率
-- 业务意义：监控业绩波动，评估活动效果
-- ==========================================
WITH daily_sales AS (
    SELECT 
        DATE(order_time) AS sale_date,
        SUM(payment_amount) AS daily_amt
    FROM orders
    GROUP BY DATE(order_time)
)
SELECT 
    sale_date AS '日期',
    daily_amt AS '当日销售额',
    LAG(daily_amt, 1) OVER(ORDER BY sale_date) AS '前一日销售额',
    ROUND(
        (daily_amt - LAG(daily_amt, 1) OVER(ORDER BY sale_date)) 
        / LAG(daily_amt, 1) OVER(ORDER BY sale_date) * 100, 
        2
    ) AS '环比增长率(%)'
FROM daily_sales
ORDER BY sale_date;
-- ==========================================
-- 3. 用户下单时间间隔（判断复购周期）
-- 业务意义：设计催付/召回策略的时间窗口
-- ==========================================
WITH user_orders AS (
    SELECT 
        user_name,
        order_time,
        ROW_NUMBER() OVER(PARTITION BY user_name ORDER BY order_time) AS order_seq,
        LAG(order_time, 1) OVER(PARTITION BY user_name ORDER BY order_time) AS prev_order_time
    FROM orders
)
SELECT 
    user_name AS '用户名',
    order_seq AS '第几单',
    order_time AS '本次下单时间',
    prev_order_time AS '上次下单时间',
    TIMESTAMPDIFF(DAY, prev_order_time, order_time) AS '距上次间隔(天)'
FROM user_orders
WHERE order_seq > 1  -- 只看第2单及以后
ORDER BY user_name, order_seq
LIMIT 30;