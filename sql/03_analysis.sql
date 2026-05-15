-- ============================================
-- 03_analysis.sql
-- 电商订单数据分析查询
-- ============================================

USE ecommerce_analysis;

-- ============================================
-- 一、销售额分析
-- ============================================

-- 1. 总销售额
SELECT SUM(payment_amount) AS total_sales FROM orders;

-- 2. 各平台销售额占比
SELECT
    platform_type,
    SUM(payment_amount) AS platform_sales,
    ROUND(SUM(payment_amount) * 100.0 / (SELECT SUM(payment_amount) FROM orders), 2) AS sales_ratio
FROM orders
GROUP BY platform_type
ORDER BY platform_sales DESC;

-- ============================================
-- 二、时间维度分析
-- ============================================

-- 3. 每日销售额趋势
SELECT
    order_date,
    SUM(payment_amount) AS daily_sales,
    COUNT(*) AS daily_orders
FROM orders
GROUP BY order_date
ORDER BY order_date;

-- 4. 每小时订单分布（24小时）
SELECT
    order_hour,
    COUNT(*) AS hourly_orders,
    SUM(payment_amount) AS hourly_sales
FROM orders
GROUP BY order_hour
ORDER BY order_hour;

-- 5. 星期几订单分布
SELECT
    weekday,
    COUNT(*) AS weekday_orders,
    SUM(payment_amount) AS weekday_sales
FROM orders
GROUP BY weekday
ORDER BY FIELD(weekday, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday');

-- ============================================
-- 三、商品分析
-- ============================================

-- 6. 商品销售额 TOP10
SELECT
    product_no,
    SUM(payment_amount) AS product_sales,
    COUNT(*) AS product_orders,
    ROUND(AVG(payment_amount), 2) AS avg_order_amount
FROM orders
GROUP BY product_no
ORDER BY product_sales DESC
LIMIT 10;

-- ============================================
-- 四、用户分析
-- ============================================

-- 7. 用户消费金额 TOP10
SELECT
    username,
    SUM(payment_amount) AS user_spending,
    COUNT(*) AS user_orders,
    ROUND(AVG(payment_amount), 2) AS avg_order_amount
FROM orders
GROUP BY username
ORDER BY user_spending DESC
LIMIT 10;

-- 8. 高价值用户识别（消费超 1 万的用户）
SELECT
    username,
    SUM(payment_amount) AS total_spending,
    COUNT(*) AS order_count
FROM orders
GROUP BY username
HAVING SUM(payment_amount) > 10000
ORDER BY total_spending DESC;

-- ============================================
-- 五、渠道分析
-- ============================================

-- 9. 各渠道转化率（付款率）
SELECT
    channel_no,
    COUNT(*) AS total_orders,
    SUM(CASE WHEN is_refund = '否' THEN 1 ELSE 0 END) AS paid_orders,
    ROUND(SUM(CASE WHEN is_refund = '否' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS conversion_rate
FROM orders
GROUP BY channel_no
ORDER BY conversion_rate DESC;

-- ============================================
-- 六、7日移动平均（趋势分析）
-- ============================================

-- 10. 带7日移动平均的日销售趋势
SELECT
    order_date,
    daily_sales,
    AVG(daily_sales) OVER (
        ORDER BY order_date
        ROWS BETWEEN 3 PRECEDING AND 3 FOLLOWING
    ) AS moving_avg_7day
FROM (
    SELECT order_date, SUM(payment_amount) AS daily_sales
    FROM orders
    GROUP BY order_date
) AS daily_data
ORDER BY order_date;