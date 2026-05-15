USE ecommerce_analysis;

LOAD DATA INFILE 'D:/ecommerce_analysis/data/cleaned_orders.csv'
INTO TABLE orders
FIELDS TERMINATED BY ','
ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS;