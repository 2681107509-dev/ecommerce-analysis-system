USE ecommerce_analysis;

-- 1. 平台销售额分析
SELECT
    platform_type,
    ROUND(SUM(payment_amount),2) AS total_sales
FROM orders
GROUP BY platform_type
ORDER BY total_sales DESC;

-- 2. TOP10 商品
SELECT
    product_id,
    ROUND(SUM(payment_amount),2) AS sales
FROM orders
GROUP BY product_id
ORDER BY sales DESC
LIMIT 10;

-- 3. 每日销售趋势
SELECT
    DATE(order_time) AS order_date,
    ROUND(SUM(payment_amount),2) AS daily_sales
FROM orders
GROUP BY order_date
ORDER BY order_date;

-- 4. 高价值用户
SELECT
    user_name,
    ROUND(SUM(payment_amount),2) AS total_spent
FROM orders
GROUP BY user_name
ORDER BY total_spent DESC
LIMIT 10;