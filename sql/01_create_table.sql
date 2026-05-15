CREATE DATABASE IF NOT EXISTS ecommerce_analysis;

USE ecommerce_analysis;

CREATE TABLE orders (
    order_seq INT,
    order_id VARCHAR(50),
    user_name VARCHAR(50),
    product_id VARCHAR(50),
    order_amount DECIMAL(10,2),
    payment_amount DECIMAL(10,2),
    channel_id VARCHAR(20),
    platform_type VARCHAR(20),
    order_time DATETIME,
    payment_time DATETIME,
    is_refund VARCHAR(10),
    discount_amount DECIMAL(10,2),
    payment_duration_sec DECIMAL(10,2),
    order_date DATE,
    order_hour INT,
    weekday VARCHAR(20)
);