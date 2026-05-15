-- ============================================
-- 01_create_table.sql
-- 创建电商订单数据表
-- ============================================

-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS ecommerce_analysis;
USE ecommerce_analysis;

-- 创建订单表
DROP TABLE IF EXISTS orders;

CREATE TABLE orders (
    id              INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    order_seq       INT COMMENT '订单顺序编号',
    order_no        VARCHAR(50) NOT NULL UNIQUE COMMENT '订单号',
    username        VARCHAR(50) NOT NULL COMMENT '用户名',
    product_no      VARCHAR(20) NOT NULL COMMENT '商品编号',
    order_amount    DECIMAL(10,2) COMMENT '订单金额',
    payment_amount  DECIMAL(10,2) COMMENT '付款金额',
    channel_no      VARCHAR(20) COMMENT '渠道编号',
    platform_type   VARCHAR(20) COMMENT '平台类型',
    order_time      DATETIME COMMENT '下单时间',
    payment_time    DATETIME COMMENT '付款时间',
    is_refund       VARCHAR(5) COMMENT '是否退款',
    discount_amount DECIMAL(10,2) COMMENT '优惠金额',
    pay_duration    INT COMMENT '支付耗时_秒',
    order_date      DATE COMMENT '下单日期',
    order_hour      INT COMMENT '下单小时',
    weekday         VARCHAR(20) COMMENT '星期几',
    INDEX idx_order_date (order_date),
    INDEX idx_platform (platform_type),
    INDEX idx_product (product_no),
    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='电商订单表';

-- 创建商品表（用于商品维度分析）
DROP TABLE IF EXISTS products;

CREATE TABLE products (
    product_no   VARCHAR(20) PRIMARY KEY COMMENT '商品编号',
    product_name VARCHAR(100) COMMENT '商品名称（可扩展）',
    category     VARCHAR(50) COMMENT '商品分类（可扩展）'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品表';

-- 创建用户表（用于用户维度分析）
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    username   VARCHAR(50) PRIMARY KEY COMMENT '用户名',
    user_level VARCHAR(20) COMMENT '用户等级（可扩展）',
    register_date DATE COMMENT '注册日期（可扩展）'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';