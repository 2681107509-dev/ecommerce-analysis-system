USE ecommerce_analysis;

LOAD DATA INFILE 'D:/ecommerce_analysis/data/cleaned_orders.csv'
INTO TABLE orders
FIELDS TERMINATED BY ','
ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS
(order_seq, order_id, user_name, product_id, order_amount, payment_amount, channel_id, platform_type, order_time, payment_time, is_refund, discount_amount, payment_duration_sec, order_date, order_hour, weekday);