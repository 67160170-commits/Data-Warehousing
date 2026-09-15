SELECT store_name, product_name, SUM(amount) AS revenue
FROM sales
WHERE month = '2026-09' 
  AND category = 'Drink'
  AND province IN ('Bangkok', 'Chonburi')
GROUP BY store_name, product_name
ORDER BY store_name, product_name;
