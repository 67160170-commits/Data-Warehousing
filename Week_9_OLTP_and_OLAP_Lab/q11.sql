-- ก่อน JOIN: นับแถวและยอด fact_sales โดยตรง
SELECT 
  'fact_sales' AS source,
  COUNT(*) AS line_count,
  SUM(quantity * unit_price) AS revenue
FROM fact_sales
UNION ALL
-- หลัง JOIN: view sales
SELECT 
  'sales_view' AS source,
  COUNT(*) AS line_count,
  SUM(amount) AS revenue
FROM sales;

-- ตรวจ Foreign Key violations
-- PRAGMA foreign_key_check;
