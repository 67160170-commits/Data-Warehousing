-- รหัสนักศึกษา 67160170
-- AI assistance: OpenAI ChatGPT / Codex; queries verified against supplied CSVs.
-- Run from C:/DW-Lab: .read submission/67160170.sql

-- แก้ path ให้ตรงตำแหน่งที่เก็บ CSV ในเครื่อง (DuckDB Desktop/CLI)
CREATE OR REPLACE TABLE products AS SELECT * FROM read_csv_auto('products.csv');
CREATE OR REPLACE TABLE customers AS SELECT * FROM read_csv_auto('customers.csv');
CREATE OR REPLACE TABLE orders AS SELECT * FROM read_csv_auto('orders.csv');
-- สถานะ Completed เท่านั้นคือรายได้จริง
CREATE OR REPLACE VIEW fact_sales AS
SELECT o.order_id, CAST(o.order_date AS DATE) AS order_date,
       o.customer_id, o.product_id, o.quantity, o.unit_price, o.discount_pct,
       o.channel,
       ROUND(o.quantity * o.unit_price * (1 - o.discount_pct/100.0),2) AS net_sales
FROM orders o WHERE o.status='Completed';
SELECT COUNT(*) AS n_orders FROM orders;
SELECT COUNT(*) AS n_completed FROM fact_sales;


-- A1
SELECT order_id, order_date, quantity, channel FROM orders ORDER BY order_id LIMIT 10;

-- A2
SELECT * FROM orders WHERE status = 'Completed' AND channel = 'ออนไลน์' ORDER BY order_date DESC, order_id DESC LIMIT 10;

-- A3
SELECT category, COUNT(*) AS product_count FROM products GROUP BY category ORDER BY product_count DESC, category;

-- A4
SELECT o.order_id, p.product_name, o.quantity, o.unit_price FROM orders o INNER JOIN products p ON o.product_id = p.product_id ORDER BY o.order_id;

-- A5
SELECT c.province, ROUND(SUM(f.net_sales),2) AS net_sales FROM fact_sales f JOIN customers c ON f.customer_id=c.customer_id GROUP BY c.province ORDER BY net_sales DESC;

-- A6
SELECT p.category, ROUND(SUM(f.net_sales),2) AS net_sales FROM fact_sales f JOIN products p ON f.product_id=p.product_id GROUP BY p.category ORDER BY net_sales DESC;

-- A7
SELECT c.customer_id, c.customer_name, ROUND(SUM(f.net_sales),2) AS monetary FROM fact_sales f JOIN customers c ON f.customer_id=c.customer_id GROUP BY c.customer_id,c.customer_name ORDER BY monetary DESC,c.customer_id LIMIT 5;

-- A8
SELECT p.product_id,p.product_name,ROUND(SUM(f.net_sales),2) AS net_sales FROM fact_sales f JOIN products p ON f.product_id=p.product_id GROUP BY p.product_id,p.product_name HAVING SUM(f.net_sales)>2000 ORDER BY net_sales DESC;

-- B1
CREATE OR REPLACE VIEW dim_customer AS SELECT * FROM customers;
CREATE OR REPLACE VIEW dim_product AS SELECT * FROM products;
CREATE OR REPLACE VIEW dim_date AS
SELECT DISTINCT order_date AS date_key, year(order_date) AS year, month(order_date) AS month, day(order_date) AS day FROM fact_sales;
CREATE OR REPLACE VIEW dim_channel AS SELECT DISTINCT channel AS channel_key FROM orders;
SELECT 'orders' AS table_name, COUNT(*) AS rows FROM orders UNION ALL SELECT 'customers',COUNT(*) FROM customers UNION ALL SELECT 'products',COUNT(*) FROM products UNION ALL SELECT 'fact_sales',COUNT(*) FROM fact_sales;

-- B2
CREATE OR REPLACE VIEW mart_monthly_sales AS
SELECT CAST(DATE_TRUNC('month',f.order_date) AS DATE) AS sales_month,p.category,f.channel,
ROUND(SUM(f.net_sales),2) AS net_sales,COUNT(*) AS transaction_count
FROM fact_sales f JOIN products p ON f.product_id=p.product_id
GROUP BY 1,2,3;
SELECT * FROM mart_monthly_sales ORDER BY sales_month,category,channel;

-- B3
SELECT 'missing_customer_id' AS issue, COUNT(*) AS issue_count FROM orders WHERE customer_id IS NULL OR TRIM(customer_id)=''
UNION ALL SELECT 'invalid_quantity',COUNT(*) FROM orders WHERE quantity IS NULL OR quantity<=0 OR quantity<>FLOOR(quantity)
UNION ALL SELECT 'unknown_product_id',COUNT(*) FROM orders o LEFT JOIN products p ON o.product_id=p.product_id WHERE p.product_id IS NULL;

-- C1
CREATE OR REPLACE VIEW daily_sales AS SELECT order_date,ROUND(SUM(net_sales),2) AS net_sales FROM fact_sales GROUP BY order_date;
SELECT order_date,net_sales,ROUND(AVG(net_sales) OVER (ORDER BY order_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW),2) AS moving_avg_7_rows FROM daily_sales ORDER BY order_date;

-- C2
CREATE OR REPLACE VIEW customer_features AS
SELECT c.customer_id,MAX(f.order_date) AS last_order,COUNT(DISTINCT f.order_id) AS frequency,COALESCE(ROUND(SUM(f.net_sales),2),0) AS monetary
FROM customers c LEFT JOIN fact_sales f ON c.customer_id=f.customer_id GROUP BY c.customer_id;
SELECT * FROM customer_features ORDER BY monetary DESC,customer_id;

-- C1_calendar
WITH calendar AS (SELECT CAST(d AS DATE) AS order_date FROM generate_series(DATE '2026-07-01',DATE '2026-09-30',INTERVAL 1 DAY) t(d)), filled AS (SELECT c.order_date,COALESCE(s.net_sales,0) AS net_sales FROM calendar c LEFT JOIN daily_sales s USING(order_date)) SELECT *,ROUND(AVG(net_sales) OVER (ORDER BY order_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW),2) AS moving_avg_7_days FROM filled ORDER BY order_date;

-- business
SELECT channel,COUNT(*) AS transaction_count,ROUND(SUM(net_sales),2) AS net_sales FROM fact_sales GROUP BY channel ORDER BY net_sales DESC;

-- totals
SELECT COUNT(*) AS transactions,ROUND(SUM(net_sales),2) AS net_sales,COUNT(DISTINCT order_date) AS selling_days,MIN(order_date) AS first_date,MAX(order_date) AS last_date FROM fact_sales;