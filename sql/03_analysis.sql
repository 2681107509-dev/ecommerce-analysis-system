-- ==========================================
-- 1. 用户首次下单日期（留存分析基准）
-- 业务意义：确定用户生命周期起点，计算留存分母
-- ==========================================
SELECT 
    user_name,
    MIN(DATE(order_time)) AS first_order_date,
    COUNT(*) AS total_orders,
    SUM(payment_amount) AS total_spent
FROM orders
GROUP BY user_name
ORDER BY first_order_date
LIMIT 20;
-- ==========================================
-- 2. 次日留存率分析
-- 业务意义：衡量新用户粘性和产品吸引力
-- ==========================================
WITH user_first_date AS (
    -- 每个用户的首次下单日期
    SELECT 
        user_name,
        MIN(DATE(order_time)) AS first_date
    FROM orders
    GROUP BY user_name
),
user_next_day AS (
    -- 统计用户在首单后第2天是否有下单
    SELECT 
        o.user_name,
        u.first_date,
        MAX(CASE 
            WHEN DATEDIFF(DATE(o.order_time), u.first_date) = 1 
            THEN 1 ELSE 0 
        END) AS has_next_day_order
    FROM orders o
    JOIN user_first_date u ON o.user_name = u.user_name
    GROUP BY o.user_name, u.first_date
)
SELECT 
    COUNT(DISTINCT user_name) AS '首日下单用户数',
    SUM(has_next_day_order) AS '次日仍下单用户数',
    ROUND(SUM(has_next_day_order) / COUNT(DISTINCT user_name) * 100, 2) AS '次日留存率(%)'
FROM user_next_day;
-- ==========================================
-- 3. 7日/30日留存率（完整留存矩阵）
-- 业务意义：评估用户长期价值，指导运营策略
-- ==========================================
WITH user_first_date AS (
    SELECT 
        user_name,
        MIN(DATE(order_time)) AS first_date
    FROM orders
    GROUP BY user_name
),
retention_calc AS (
    SELECT 
        o.user_name,
        u.first_date,
        MAX(CASE WHEN DATEDIFF(DATE(o.order_time), u.first_date) BETWEEN 1 AND 7 THEN 1 ELSE 0 END) AS retained_7d,
        MAX(CASE WHEN DATEDIFF(DATE(o.order_time), u.first_date) BETWEEN 8 AND 30 THEN 1 ELSE 0 END) AS retained_30d
    FROM orders o
    JOIN user_first_date u ON o.user_name = u.user_name
    GROUP BY o.user_name, u.first_date
)
SELECT 
    COUNT(DISTINCT user_name) AS '总用户数',
    SUM(retained_7d) AS '7日内复购用户',
    ROUND(SUM(retained_7d) / COUNT(DISTINCT user_name) * 100, 2) AS '7日留存率(%)',
    SUM(retained_30d) AS '30日内复购用户',
    ROUND(SUM(retained_30d) / COUNT(DISTINCT user_name) * 100, 2) AS '30日留存率(%)'
FROM retention_calc;
-- ==========================================
-- 4. RFM 模型：计算三维度指标
-- R (Recency)：最近一次消费距今天数
-- F (Frequency)：消费频次
-- M (Monetary)：消费金额
-- 业务意义：用户分层、精准营销的基础
-- ==========================================
SELECT 
    user_name,
    DATEDIFF(NOW(), MAX(order_time)) AS R,  -- 最近消费距今天数
    COUNT(order_id) AS F,                     -- 消费频次
    ROUND(SUM(payment_amount), 2) AS M        -- 消费金额
FROM orders
GROUP BY user_name
ORDER BY R ASC, F DESC, M DESC;
-- ==========================================
-- RFM 最终版（基于你的真实数据分布）
-- ==========================================
WITH rfm_base AS (
    SELECT 
        user_name,
        DATEDIFF(
            (SELECT MAX(DATE(order_time)) FROM orders), 
            MAX(DATE(order_time))
        ) AS R,
        COUNT(order_id) AS F,
        SUM(payment_amount) AS M
    FROM orders
    GROUP BY user_name
),
rfm_score AS (
    SELECT 
        user_name, R, F, M,
        -- R 打分（适配你的数据：平均147天，最大364天）
        CASE 
            WHEN R <= 30 THEN 5      -- 最近1个月
            WHEN R <= 90 THEN 4      -- 最近3个月
            WHEN R <= 180 THEN 3     -- 最近半年
            WHEN R <= 270 THEN 2     -- 最近9个月
            ELSE 1                    -- 9个月以上
        END AS R_score,
        -- F 打分（适配你的数据：平均1.31单，最大7单）
        CASE 
            WHEN F >= 6 THEN 5       -- 超级忠诚
            WHEN F >= 4 THEN 4       -- 高频复购
            WHEN F >= 2 THEN 3       -- 有复购
            WHEN F = 1 THEN 2        -- 只买1次
            ELSE 1
        END AS F_score,
        -- M 打分（适配你的数据：平均1303元，最大3.2万）
        CASE 
            WHEN M >= 5000 THEN 5    -- 高价值
            WHEN M >= 2000 THEN 4    -- 中高价值
            WHEN M >= 1000 THEN 3    -- 中等价值
            WHEN M >= 500 THEN 2     -- 低价值
            ELSE 1                    -- 极低价值
        END AS M_score
    FROM rfm_base
)
SELECT 
    user_name, R, F, M,
    R_score, F_score, M_score,
    (R_score + F_score + M_score) AS total_score,
    CASE 
        WHEN R_score >= 4 AND F_score >= 4 AND M_score >= 4 THEN '重要价值用户'
        WHEN R_score >= 4 AND F_score >= 3 AND M_score <= 2 THEN '重要发展用户'
        WHEN R_score <= 2 AND F_score >= 4 AND M_score >= 4 THEN '重要保持用户'
        WHEN R_score <= 2 AND F_score <= 2 AND M_score <= 2 THEN '流失用户'
        ELSE '一般用户'
    END AS user_segment
FROM rfm_score
ORDER BY total_score DESC, M DESC;
-- 统计各分层用户数量
WITH rfm_base AS (
    SELECT 
        user_name,
        DATEDIFF((SELECT MAX(DATE(order_time)) FROM orders), MAX(DATE(order_time))) AS R,
        COUNT(order_id) AS F,
        SUM(payment_amount) AS M
    FROM orders
    GROUP BY user_name
),
rfm_score AS (
    SELECT 
        user_name, R, F, M,
        CASE WHEN R <= 30 THEN 5 WHEN R <= 90 THEN 4 WHEN R <= 180 THEN 3 WHEN R <= 270 THEN 2 ELSE 1 END AS R_score,
        CASE WHEN F >= 6 THEN 5 WHEN F >= 4 THEN 4 WHEN F >= 2 THEN 3 WHEN F = 1 THEN 2 ELSE 1 END AS F_score,
        CASE WHEN M >= 5000 THEN 5 WHEN M >= 2000 THEN 4 WHEN M >= 1000 THEN 3 WHEN M >= 500 THEN 2 ELSE 1 END AS M_score
    FROM rfm_base
)
SELECT 
    CASE 
        WHEN R_score >= 4 AND F_score >= 4 AND M_score >= 4 THEN '重要价值用户'
        WHEN R_score >= 4 AND F_score >= 3 AND M_score <= 2 THEN '重要发展用户'
        WHEN R_score <= 2 AND F_score >= 4 AND M_score >= 4 THEN '重要保持用户'
        WHEN R_score <= 2 AND F_score <= 2 AND M_score <= 2 THEN '流失用户'
        ELSE '一般用户'
    END AS 用户分层,
    COUNT(*) AS 用户数,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM rfm_base), 2) AS '占比(%)',
    ROUND(AVG(M), 2) AS '平均消费',
    ROUND(AVG(F), 2) AS '平均频次'
FROM rfm_score
GROUP BY 用户分层
ORDER BY 用户数 DESC;