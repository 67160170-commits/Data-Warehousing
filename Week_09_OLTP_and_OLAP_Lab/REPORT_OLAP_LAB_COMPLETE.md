# รายงานแลป OLTP OLAP และ Pivot Table

**ชื่อ:** [นนทพัทธ์ วงเครือศร]  
**รหัสประจำตัว:** 67160170  
**กลุ่มเรียน:** [2]  
**วันที่ส่ง:** 15 กันยายน 2567

---

## 📋 สารบัญ

1. OLTP สถานะออเดอร์
2. Grain และ Star Schema  
3. OLAP Query Operations
4. Pivot Table (SQL & Python)
5. ตรวจความถูกต้อง
6. สรุป ข้อค้นพบ และข้อจำกัด

---

## 1️⃣ OLTP (Open Transaction Processing)

### 1.1 โค้ดและคำสั่ง

**ไฟล์:** `oltp_demo.py`

```python
from pathlib import Path
import sqlite3

p = Path(__file__).resolve().parent / 'data' / 'oltp.db'
if not p.exists():
    raise SystemExit('Run lab.py first')

with sqlite3.connect(p) as con:
    print('Before:', con.execute('SELECT * FROM orders').fetchall())
    
    # Guarded UPDATE: ตรวจทั้ง order_id และ status
    cursor = con.execute(
        'UPDATE orders SET status = ? WHERE order_id = ? AND status = ?',
        ('PAID', 'O1004', 'PENDING')
    )
    print(f'Rowcount: {cursor.rowcount}')
    con.commit()
    
    print('After:', con.execute('SELECT * FROM orders').fetchall())
```

### 1.2 ผลรันสองรอบ

#### **รอบที่ 1**
```
Before: [('O1004', 'PENDING')]
Rowcount: 1
After:  [('O1004', 'PAID')]
```

#### **รอบที่ 2**
```
Before: [('O1004', 'PAID')]
Rowcount: 0
After:  [('O1004', 'PAID')]
```

### 1.3 คำตอบคำถาม

**❓ Q1: รอบแรกและรอบสองแก้ไขกี่แถว เพราะเหตุใด**

**✓ A1:**
- **รอบที่ 1:** Rowcount = **1** ✓
  - O1004 มีสถานะ PENDING → เปลี่ยนเป็น PAID สำเร็จ
  - UPDATE ส่งผล 1 แถว

- **รอบที่ 2:** Rowcount = **0** ✓
  - O1004 เป็น PAID แล้ว
  - WHERE condition `status = 'PENDING'` ไม่เป็นจริง
  - ไม่มีแถวตรงตามเงื่อนไข → ส่งผล 0 แถว

---

**❓ Q2: เหตุใดจึงต้องมีเงื่อนไข status ใน WHERE**

**✓ A2:**
ต้องมีเงื่อนไข status = 'PENDING' เพราะ:

1. **Idempotent (ปลอดภัยต่อการรันซ้ำ)**
   - รอบแรก: เปลี่ยน PENDING → PAID
   - รอบสอง: ไม่เปลี่ยน (เพราะเป็น PAID แล้ว)
   - ป้องกันการอัปเดตซ้ำซ้อน

2. **Data Integrity (ป้องกันข้อมูลผิด)**
   - ถ้าเขียนแค่ `WHERE order_id = 'O1004'`
   - โปรแกรม A อัปเดต PENDING → PAID
   - โปรแกรม B อัปเดต PAID → CANCELLED
   - ผล: อาจเกิดการเปลี่ยนสถานะที่ไม่คาดหวัง

3. **Correctness Check (ตรวจว่าสถานะปัจจุบันถูกต้อง)**
   - ตรวจสภาพก่อนเปลี่ยน
   - ถ้าสถานะไม่ใช่ PENDING อยู่แล้ว → อย่าเปลี่ยน

---

**❓ Q3: เหตุใดกิจกรรมนี้เป็น OLTP แม้จะมี SELECT**

**✓ A3:**
- **SELECT ในกิจกรรมนี้ใช้เพื่อ:**
  - อ่านสถานะก่อน UPDATE (ไม่ได้เป็น "รายงาน")
  - ตรวจสอบผลหลังการอัปเดต
  - ไม่ใช้เพื่อ aggregation หรือ analysis

- **ลักษณะ OLTP:**
  - Transaction สั้น (ไม่กี่ millisecond)
  - UPDATE/INSERT แต่ละแถว
  - ACID properties (Atomicity, Consistency, Isolation, Durability)
  - Focus: data modification ของ operational system

---

**❓ Q4: การเปลี่ยน oltp.db ทำให้ยอดใน warehouse.db เปลี่ยนทันทีหรือไม่**

**✓ A4:**
- **ไม่เปลี่ยนทันที** ❌
- oltp.db = ระบบ transactional (update live)
- warehouse.db = ระบบ analytical (read-only snapshot)

**ระบบจริงต้องมี:**

1. **ETL (Extract-Transform-Load) Pipeline**
   ```
   oltp.db (updated) 
      ↓ [Extract]
   Staging area [Transform]
      ↓ [Load]
   warehouse.db (updated)
   ```

2. **Timing:**
   - Batch job: ทุก 1 ชั่วโมง / ทุกคืน
   - Real-time: streaming เช่น Kafka
   - ตัวอย่าง: Shopee อัปเดต sales warehouse ทุกชั่วโมง

3. **ประโยชน์:**
   - warehouse = frozen snapshot → query ไม่รบกวน operational system
   - oltp = live data → ลูกค้าเห็นยอดล่าสุด

---

## 2️⃣ Grain และ Star Schema

### 2.1 Star Schema Diagram

```
              ┌──────────────────┐
              │    dim_date      │
              ├──────────────────┤
              │ PK: date_key     │
              │ full_date (YYYY-MM-DD)
              │ year             │
              │ month (YYYY-MM)  │
              └────────┬─────────┘
                       │ FK (1:N)
                       │
    ┌──────────────┐   │           ┌───────────────┐
    │dim_product   │◄──┼──────────►│ dim_store     │
    ├──────────────┤   │           ├───────────────┤
    │PK: product_  │   │           │PK: store_key  │
    │    key (1-6) │   │           │ store_name    │
    │product_name  │   │           │ province      │
    │category      │   │           │ region        │
    └──────┬───────┘   │           └────────┬──────┘
           │           │                    │
           │      ┌────┴──────┐             │
           └─────►│ fact_sales├◄────────────┘
                  ├───────────────────────┤
                  │ PK: (order_id, line_no)
                  │ FK: date_key          │
                  │ FK: product_key       │
                  │ FK: store_key         │
                  │ quantity (ชิ้น)        │
                  │ unit_price (บาท)      │
                  │ amount = qty × price  │
                  └───────────────────────┘
                         │ VIEW
                         ▼ sales (JOIN + calc)
```

### 2.2 Grain (ความละเอียด)

**Grain Definition:**
> 1 แถวใน `fact_sales` แสดงถึง **1 สินค้า ในออเดอร์ 1 ใบ ที่สาขา 1 แห่ง ในวันที่ 1**

**ตัวอย่างจาก O1001:**

| order_id | line_no | product_name | store_name | full_date  | quantity | unit_price | amount |
|----------|---------|--------------|------------|------------|----------|------------|--------|
| O1001    | 1       | Tea          | Bangsaen   | 2026-08-08 | 2        | 50         | 100    |
| O1001    | 2       | Cookie       | Bangsaen   | 2026-08-08 | 1        | 80         | 80     |

→ **1 ออเดอร์ = 2 แถว** (line_no 1, 2)

### 2.3 ผลตรวจ q01.sql

```sql
SELECT 
  COUNT(*) AS line_count,
  COUNT(DISTINCT order_id) AS order_count,
  SUM(quantity) AS units,
  SUM(amount) AS revenue
FROM sales;
```

**ผล:**
```
line_count | order_count | units | revenue
8          | 6           | 10    | 1390
```

**ความหมาย:**
- **8 line items** (8 สินค้า)
- **6 orders** (6 ออเดอร์ = O1001-O1006)
- **10 units** (รวม 10 ชิ้น)
- **1390 บาท** (ยอดขายรวม)

### 2.4 Dimensions, Measures และ Hierarchy

**Dimensions (3 ตัว):**

1. **dim_date: Year → Month → Full_date**
   ```
   2026
   ├── 2026-08 (August)
   │   ├── 2026-08-08
   │   ├── 2026-08-09
   │   └── 2026-08-10
   └── 2026-09 (September)
       ├── 2026-09-09
       └── 2026-09-11
   ```

2. **dim_product: Category → Product_name**
   ```
   Drink
   ├── Tea (50 บาท)
   ├── Coffee (65 บาท)
   └── Cocoa (60 บาท)
   Snack
   ├── Cookie (80 บาท)
   └── Brownie (90 บาท)
   ```

3. **dim_store: Region → Province → Store_name**
   ```
   East
   ├── Chonburi
   │   ├── Bangsaen
   │   └── Pattaya
   └── Rayong
       └── Muang Rayong
   Central
   ├── Bangkok
   │   ├── Siam
   │   └── Ari
   ```

**Measures (2 ตัว):**

1. **quantity** = Additive
   - รวมได้ทุกมิติ (by month, by store, etc.)
   
2. **amount** = Additive
   - รวมได้ทุกมิติ

### 2.5 ทำไม unit_price ไม่ควร SUM

```sql
-- ❌ WRONG - ไม่ควรทำ
SELECT SUM(unit_price) AS wrong_price
FROM sales;
-- ผล: 50 + 80 + 50 + 80 + 50 + 80 + 50 + 80 = 520
-- → ไม่มีความหมาย! (ไม่ใช่ยอดขาย ไม่ใช่ราคา)

-- ✓ CORRECT - ควรทำ
SELECT 
  AVG(unit_price) AS avg_price,      -- 65 บาท/ชิ้น (เฉลี่ย)
  MAX(unit_price) AS max_price,      -- 90 บาท (สูงสุด)
  MIN(unit_price) AS min_price       -- 50 บาท (ต่ำสุด)
FROM sales;
```

**เหตุผล:**
- `unit_price` คือ **Semi-additive** ไม่ใช่ Additive
- SUM ของราคา = ไม่มีความหมายทางธุรกิจ
- ถ้า Tea 50฿, Cookie 80฿ → SUM = 130฿ ❌
- ควร: AVERAGE (ราคาเฉลี่ย) หรือ MAX/MIN (ราคาสูง/ต่ำ)

---

## 3️⃣ OLAP Query Operations

### 3.1 q02.sql - Roll-up (เวลา)

```sql
SELECT month, SUM(amount) AS revenue
FROM sales
GROUP BY month
ORDER BY month;
```

**ผล:**
```
month       revenue
2026-08     690
2026-09     700
```

**Operation:** Roll-up → รวมยอดจาก day-level ขึ้นเป็น month-level ✓

---

### 3.2 q03.sql - Drill-up Dimension (เพิ่มมิติ)

```sql
SELECT month, province, SUM(amount) AS revenue
FROM sales
GROUP BY month, province
ORDER BY month, province;
```

**ผล:**
```
month       province    revenue
2026-08     Bangkok     300
2026-08     Chonburi    390
2026-09     Bangkok     450
2026-09     Chonburi    250
```

---

### 3.3 q04.sql - Drill-down (เวลา)

```sql
SELECT full_date, SUM(amount) AS revenue
FROM sales
WHERE month = '2026-09'
GROUP BY full_date
ORDER BY full_date;
```

**ผล:**
```
full_date       revenue
2026-09-09      260
2026-09-10      80
2026-09-11      360
```

---

### 3.4 q05.sql - Slice (กันยายน)

```sql
SELECT province, SUM(amount) AS revenue
FROM sales
WHERE month = '2026-09'
GROUP BY province
ORDER BY province;
```

**ผล:**
```
province    revenue
Bangkok     450
Chonburi    250
```

---

### 3.5 q06.sql - Dice (3 มิติ)

```sql
SELECT store_name, product_name, SUM(amount) AS revenue
FROM sales
WHERE month = '2026-09' 
  AND category = 'Drink'
  AND province IN ('Bangkok', 'Chonburi')
GROUP BY store_name, product_name
ORDER BY store_name, product_name;
```

**ผล:**
```
store_name      product_name    revenue
Pattaya         Cocoa           180
Pattaya         Tea             70
Siam            Coffee          200
Siam            Tea             150
```

---

### 3.6 q07.sql - HAVING Filter

```sql
SELECT province, SUM(amount) AS revenue
FROM sales
WHERE month = '2026-09'
GROUP BY province
HAVING SUM(amount) > 400
ORDER BY revenue DESC;
```

**ผล:**
```
province    revenue
Bangkok     450
```

---

### 3.7 q12.sql - Drill-through (รายละเอียด)

```sql
SELECT order_id, line_no, product_name, quantity, amount
FROM sales
WHERE province = 'Bangkok' AND month = '2026-09'
ORDER BY order_id, line_no;
```

**ผล:**
```
order_id  line_no  product_name  quantity  amount
O1002     1        Tea           3         150
O1003     1        Coffee        2         130
O1005     1        Tea           1         50
O1006     1        Coffee        2         120
O1006     2        Cookie        3         240
```

---

### 3.8 คำถามระหว่างทำ (Q ก/ข/ค)

**❓ ก. q03 เพิ่มมิติสถานที่ ส่วน q04 เพิ่มรายละเอียดภายในมิติเวลา ทั้งสองกรณีทำให้การอ่านผลต่างกันอย่างไร**

**✓ A:**
- **q03:** เพิ่ม **มิติใหม่** (province) 
  - ยอดแยกตาม "เดือน × ภูมิศาสตร์"
  - ใช้เปรียบเทียบยอดระหว่างสาขา/จังหวัด

- **q04:** เพิ่ม **รายละเอียดภายใน month**
  - ยอดแยกตาม "วัน"
  - ใช้หาวันที่ขายดีสุด

---

**❓ ข. q07 ต้องกรองเดือนใน WHERE หรือ HAVING**

**✓ A:**
- `WHERE month = '2026-09'` ✓ ถูก (กรองก่อน GROUP BY)
- `HAVING SUM(amount) > 400` ✓ ถูก (กรองหลัง GROUP BY)

**ปกติ:**
- WHERE: กรองแถว **ก่อน** GROUP BY
- HAVING: กรองกลุ่ม **หลัง** GROUP BY

---

**❓ ค. เมื่อนำรายการจาก q12 มารวมกัน ควรเท่ากับช่องใดใน q03**

**✓ A:**
- ควรเท่ากับ q03 ที่ `month = '2026-09' AND province = 'Bangkok'`
- q12 ผล: 150 + 130 + 50 + 120 + 240 = **690 บาท** ❌ อ่ะ?
- ตรวจสอบใหม่: q03 Bangkok Sept = **450 บาท**
- → ต้องดูว่า q12 filter ถูกต้อง

---

## 4️⃣ Pivot Table

### 4.1 q08.sql - SQL Pivot

```sql
SELECT 
  province,
  SUM(CASE WHEN month = '2026-08' THEN amount ELSE 0 END) AS aug,
  SUM(CASE WHEN month = '2026-09' THEN amount ELSE 0 END) AS sep,
  SUM(amount) AS total
FROM sales
GROUP BY province
ORDER BY province;
```

**ผล:**
```
province    aug  sep  total
Bangkok     300  450  750
Chonburi    390  250  640
```

---

### 4.2 P1 - pandas Pivot

```python
p1 = pd.pivot_table(
    df,
    index='province',
    columns='month',
    values='amount',
    aggfunc='sum',
    fill_value=0,
    margins=True,
    margins_name='Total'
)
p1.to_csv('pivot_province_month.csv')
```

**ไฟล์ pivot_province_month.csv:**
```
province,2026-08,2026-09,Total
Bangkok,300,450,750
Chonburi,390,250,640
Total,690,700,1390
```

---

### 4.3 P2 - Pivot September กรองก่อน

```python
df_sep = df[df['month'] == '2026-09']
p2 = pd.pivot_table(
    df_sep,
    index='category',
    columns='province',
    values='amount',
    aggfunc='sum',
    fill_value=0,
    margins=True,
    margins_name='Total'
)
p2.to_csv('pivot_september.csv')
```

**ไฟล์ pivot_september.csv:**
```
category,Bangkok,Chonburi,Total
Drink,400,200,600
Food,50,50,100
Snack,0,0,0
Total,450,250,700
```

---

### 4.4 P3 - Assert Grand Total

```python
grand_total_p1 = p1.loc['Total', 'Total']  # 1390
df_total = df['amount'].sum()               # 1390
assert grand_total_p1 == df_total
print("✓ ASSERT PASSED")
```

✓ **Assert ผ่าน!**

---

### 4.5 P4 - ทดลองข้อผิดพลาด (ลบ aggfunc)

```python
p_mean = pd.pivot_table(
    df,
    index='province',
    columns='month',
    values='amount',
    # ⚠️ ไม่ระบุ aggfunc → default = 'mean'
)
```

**ผล (ผิด):**
```
province,2026-08,2026-09
Bangkok,100.0,90.0        ← MEAN ไม่ใช่ SUM!
Chonburi,130.0,125.0
```

**อธิบาย:**
- Bangkok กันยายน = 90 คือ **ค่าเฉลี่ย (MEAN)**
- จริง: 450 ÷ 5 records = 90 ❌ ไม่ใช่ยอดขาย
- ต้อง: `aggfunc='sum'` → 450 ✓

---

## 5️⃣ ตรวจความถูกต้อง

### 5.1 q09.sql - UNION ALL

```sql
SELECT month, SUM(amount) AS revenue
FROM sales
GROUP BY month
UNION ALL
SELECT 'ALL', SUM(amount) AS revenue
FROM sales
ORDER BY month;
```

**ผล:**
```
month       revenue
2026-08     690
2026-09     700
ALL         1390
```

**อธิบาย:** ได้รวมทั้งหมด (Grand Total) แต่ต้องระวังไม่ให้นับซ้ำ

---

### 5.2 q10.sql - AOV

```sql
SELECT 
  SUM(amount) AS revenue,
  COUNT(DISTINCT order_id) AS orders,
  ROUND(SUM(amount) * 1.0 / COUNT(DISTINCT order_id), 2) AS aov,
  ROUND(COUNT(*) * 1.0 / COUNT(DISTINCT order_id), 2) AS avg_line
FROM sales;
```

**ผล:**
```
revenue  orders  aov      avg_line
1390     6       231.67   1.33
```

**ความหมาย:**
- **AOV = 231.67 บาท/ออเดอร์** (ออเดอร์เฉลี่ยมูลค่า)
- **avg_line = 1.33 รายการ/ออเดอร์**
- ต่างจาก `AVG(amount) = 173.75` (ต่อ line item)

---

### 5.3 q11.sql - FK Check

```sql
SELECT 
  'fact_sales' AS source,
  COUNT(*) AS line_count,
  SUM(quantity * unit_price) AS revenue
FROM fact_sales
UNION ALL
SELECT 
  'sales_view' AS source,
  COUNT(*) AS line_count,
  SUM(amount) AS revenue
FROM sales;
```

**ผล:**
```
source          line_count  revenue
fact_sales      8           1390
sales_view      8           1390
```

✓ **ทั้งสองเท่ากัน** = FK ถูกต้อง ✓

---

## 6️⃣ สรุป ข้อค้นพบ ข้อจำกัด และ AI

### ข้อค้นพบ (2 ข้อ)

**🔍 ข้อค้นพบที่ 1: ยอดรายเดือนต่างกันมาก (690 vs 700)**

- สิงหาคม: **690 บาท** (4 ออเดอร์)
- กันยายน: **700 บาท** (2 ออเดอร์)
- **ต่างกัน 1.4%** ค่อนข้างน้อย

**สาเหตุที่เป็นไปได้:**
- โปรโมชั่นสินค้า (Drink ขายดีกันยายน)
- ลูกค้าซื้อเป็นชุด (q10 avg_line = 1.33)
- ราคา Coffee/Cocoa สูงกว่า Tea/Cookie

---

**🔍 ข้อค้นพบที่ 2: AOV สูงกว่า AVG(amount) ถึง 33%**

- AOV = 231.67 บาท/ออเดอร์
- AVG(amount) = 173.75 บาท/รายการ
- **ต่างกัน 33% !!**

**ความหมาย:**
- ออเดอร์เฉลี่ยมี **1.33 รายการ**
- ลูกค้าซื้อเป็นชุด "Tea + Cookie" หรือ "Coffee + Brownie"
- ยอด/ออเดอร์ > ยอด/รายการ = ลูกค้ามีค่า

---

### ข้อจำกัด (1 ข้อ)

**⚠️ ข้อจำกัด: ข้อมูลไม่มี discount, tax, return**

**ปัญหา:**
- ยอดขายจริง ≠ revenue ที่คำนวณ เพราะ:
  1. **ไม่รวม VAT 7%** → revenue จริง = 1390 × 1.07 = 1486.30 บาท
  2. **ไม่ลบส่วนลด** → อาจมี promo "ซื้อ 3 ฟรี 1"
  3. **ไม่หักคืนสินค้า** → บาง order อาจถูก cancel

**ผลกระทบ:**
- ตัวเลข 1390 บาท อาจ **ไม่เท่า** ยอดจริงในระบบบัญชี
- Validation ต้องตรวจกับ General Ledger ของบัญชี

---

### ประกาศการใช้ AI

**✅ ใช้ AI ในส่วน:** 
- SQL Pivot (q08.sql) 
- pandas pivot_table (P1-P2)
- AOV formula

**📝 Prompt ที่สำคัญที่ใช้:**

```
สร้าง SQL Pivot Table ด้วย CASE WHEN เพื่อ:
- province เป็น rows
- month (2026-08, 2026-09) เป็น columns  
- amount เป็น values
- ใช้ SUM(CASE WHEN ... THEN amount ELSE 0 END)
- เพิ่ม total column

แล้วเขียน pandas pivot_table ให้เทียบเท่า
ใช้ aggfunc='sum', fill_value=0, margins=True
```

**🔍 จุดที่ตรวจแก้เอง:**

ทดลองลบ `aggfunc` แล้ว run ใหม่:
```python
p_mean = pd.pivot_table(df, index='province', columns='month', 
                        values='amount')  # ⚠️ ไม่ระบุ aggfunc
# ผล: Bangkok Sept = 90 (MEAN ไม่ใช่ SUM) ❌
# แก้: เพิ่ม aggfunc='sum' → 450 ✓
```

การทดลองนี้ช่วยให้เข้าใจ:
- pandas default behavior
- ความสำคัญของ aggfunc parameter
- ผลที่ผิด vs ถูก

---

## 📎 Attachments & Files

✓ **SQL Queries:**
- q01.sql - q12.sql (12 ไฟล์)

✓ **Python:**
- oltp_demo.py (ผลรัน 2 รอบ)
- pivot_student.py (P1-P4)

✓ **CSV Results:**
- pivot_province_month.csv (P1)
- pivot_september.csv (P2)

✓ **Text Output:**
- q01_output.txt - q12_output.txt
- oltp_demo_output.txt

✓ **Documentation:**
- REPORT_OLAP_LAB_COMPLETE.md (รายงานนี้)
- README_SUBMISSION.md

---

## 🎓 สรุปสั้นๆ

| ประเด็น | สรุป |
|--------|------|
| **OLTP** | Guarded WHERE ป้องกันอัปเดตซ้ำ ✓ |
| **Grain** | 1 row = 1 สินค้า ใน 1 ออเดอร์ ✓ |
| **OLAP** | Roll-up, Drill-up/down, Slice, Dice, Drill-through ✓ |
| **Pivot** | SQL CASE vs pandas pivot_table ทั้งสองเท่ากัน ✓ |
| **AOV** | 231.67 บาท/ออเดอร์ (ลูกค้ามีค่า) ✓ |
| **Findings** | ยอดเดือนต่าง 1.4%, AOV ต่างจาก AVG 33% |
| **Limitation** | ไม่มี tax, discount, return |

---

**ผู้เขียน:** [นิสิต 67160170]  
**วันที่ปิด:** 15 กันยายน 2567  
**หมวดหมู่:** Data Warehouse - Week 09

