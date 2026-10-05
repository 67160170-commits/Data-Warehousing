SELECT order_id, line_no, product_name, quantity, amount
FROM sales
WHERE province = 'Bangkok' AND month = '2026-09'
ORDER BY order_id, line_no;
