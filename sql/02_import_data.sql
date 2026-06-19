-- AI Commerce Intelligence Platform - 首次导入清洗后的订单数据
-- docker-compose 将 CSV 挂载到 /var/lib/mysql-files/cleaned_orders.csv。

LOAD DATA INFILE '/var/lib/mysql-files/cleaned_orders.csv'
INTO TABLE orders
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ','
OPTIONALLY ENCLOSED BY '"'
ESCAPED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(
    @order_seq_id,
    @order_id,
    @user_name,
    @product_id,
    @order_amount,
    @payment_amount,
    @channel_id,
    @platform_type,
    @order_time,
    @payment_time,
    @is_refund,
    @discount_amount,
    @payment_duration_sec,
    @order_date,
    @order_hour,
    @weekday
)
SET
    order_seq_id = NULLIF(TRIM(BOTH '\r' FROM @order_seq_id), ''),
    order_id = NULLIF(@order_id, ''),
    user_name = NULLIF(@user_name, ''),
    product_id = NULLIF(@product_id, ''),
    order_amount = NULLIF(@order_amount, ''),
    payment_amount = NULLIF(@payment_amount, ''),
    channel_id = NULLIF(@channel_id, ''),
    platform_type = NULLIF(@platform_type, ''),
    order_time = NULLIF(@order_time, ''),
    payment_time = NULLIF(@payment_time, ''),
    is_refund = NULLIF(@is_refund, ''),
    discount_amount = NULLIF(@discount_amount, ''),
    payment_duration_sec = NULLIF(@payment_duration_sec, ''),
    order_date = NULLIF(@order_date, ''),
    order_hour = NULLIF(@order_hour, ''),
    weekday = NULLIF(TRIM(BOTH '\r' FROM @weekday), '');
