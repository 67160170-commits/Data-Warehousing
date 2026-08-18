# ETL Lab Report

Student ID: 67160170
Name:นนทพัทธ์ วงเครือศร

## 1. Data Quality Problems Found
- `customers.csv` มี `customer_id` ซ้ำ
- `province` มีรูปแบบไม่เป็นมาตรฐาน
- `orders.csv` มี `order_id` ซ้ำ
- `order_date` มีหลายรูปแบบและมีวันที่ไม่ถูกต้อง
- `status` มีตัวพิมพ์ไม่สม่ำเสมอ
- `qty` มีค่าที่ไม่ถูกต้อง (`qty <= 0`)
- `unit_price` มีค่าที่ไม่ถูกต้อง (`unit_price <= 0`)
- `discount_pct` มีค่านอกช่วง 0–100
- `products.json` เป็น nested JSON
- `products.json` มีราคาที่เป็น string เช่น `"1,299.00"`
- `products.json` มี category ที่หายไป

## 2. Cleaning / Transformation Rules
- ลบข้อมูล `customer_id` ที่ซ้ำกัน
- Standardize `province`
- จัดการ missing values
- Flatten `products.json` ด้วย `pd.json_normalize()`
- เปลี่ยนชื่อ column ของ product ให้อยู่ในรูปแบบที่ใช้งานง่าย
- แปลง `price` เป็น numeric
- กำหนด category ที่หายไปเป็น `"Unknown"`
- ลบ `order_id` ที่ซ้ำกัน
- Parse `order_date` ที่มีหลายรูปแบบ
- Standardize `status` เป็น lowercase
- Reject record ที่ `qty <= 0`
- Reject record ที่ `unit_price <= 0`
- Reject record ที่ `discount_pct < 0` หรือ `discount_pct > 100`
- Reject record ที่วันที่ไม่ถูกต้อง
- เก็บเฉพาะ order ที่มี status เป็น `paid` หรือ `completed`
- Join orders กับ customers และ products
- คำนวณ `gross_amount`, `discount_amount` และ `sales_amount`

## 3. Rejected Records
จำนวน: 4

เหตุผลหลัก:
- ข้อมูล order ไม่ผ่านกฎ Data Quality เช่น qty, unit_price, discount_pct หรือ order_date ไม่ถูกต้อง

## 4. ETL Validation
- Valid transformed rows: 100
- Warehouse rows: 100
- Duplicate order_id: 0
- Source total sales: 192074.66
- Warehouse total sales: 192074.66
- Validation status: PASS

## 5. Idempotency Test
จำนวน fact_sales หลัง run ครั้งที่ 1: 100

จำนวน fact_sales หลัง run ครั้งที่ 2: 100

อธิบายผล:
เมื่อรัน Pipeline ซ้ำ จำนวนข้อมูลใน `fact_sales` ยังคงเป็น 100 records เท่าเดิม และไม่เกิด `order_id` ซ้ำ เพราะกำหนด `order_id` ให้เป็น UNIQUE และป้องกันการ insert record เดิมซ้ำ ทำให้ Pipeline สามารถ rerun ได้โดยไม่ทำให้ข้อมูลใน Warehouse เพิ่มซ้ำ
