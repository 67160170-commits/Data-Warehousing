# 📦 ไฟล์ส่งงาน OLAP Lab

## 📋 เนื้อหา ZIP

```
67160170_olap_lab.zip
├── SQL Files (q01.sql - q12.sql)
│   ├── q01.sql          ← Grain: line_count, order_count, units, revenue
│   ├── q02.sql          ← Roll-up by month
│   ├── q03.sql          ← Drill-up by month + province
│   ├── q04.sql          ← Drill-down by date (September)
│   ├── q05.sql          ← Slice September by province
│   ├── q06.sql          ← Dice September Drink Bangkok/Chonburi
│   ├── q07.sql          ← HAVING province > 400 baht
│   ├── q08.sql          ← SQL Pivot CASE WHEN
│   ├── q09.sql          ← UNION ALL with grand total
│   ├── q10.sql          ← AOV (Average Order Value)
│   ├── q11.sql          ← FK Check before/after JOIN
│   └── q12.sql          ← Drill-through Bangkok September
│
├── Python Files
│   ├── oltp_demo.py     ← UPDATE order status (guarded WHERE)
│   └── pivot_student.py ← P1-P4 Pivot Table
│
├── Output & Results
│   ├── q01_output.txt   ← Output results (tab-separated)
│   ├── q02_output.txt
│   ├── ... (q03 - q12)
│   ├── oltp_demo_output.txt    ← Two rounds of OLTP
│   ├── pivot_province_month.csv ← P1 Pivot
│   └── pivot_september.csv      ← P2 Pivot
│
├── Report
│   └── REPORT_OLAP_LAB.md  ← 4-page report (complete answers)
│
└── README_SUBMISSION.md ← This file
```

---

## 🚀 วิธีใช้ไฟล์

### 1. **SQL Queries** (q01.sql - q12.sql)

รัน queries ครั้งละหนึ่ง:
```bash
python query.py data/warehouse.db q01.sql
python query.py data/warehouse.db q02.sql
# ... ฯลฯ
```

### 2. **OLTP Demo** (oltp_demo.py)

รัน 2 รอบ ตามที่ระบุในข้อ:
```bash
python oltp_demo.py  # รอบที่ 1
python oltp_demo.py  # รอบที่ 2
```

**ผลที่คาดหวัง:**
- รอบ 1: Rowcount = 1
- รอบ 2: Rowcount = 0

### 3. **Pivot Table** (pivot_student.py)

```bash
python pivot_student.py
```

**ไฟล์ที่สร้าง:**
- `pivot_province_month.csv` (P1)
- `pivot_september.csv` (P2)

---

## 📄 รายงาน (REPORT_OLAP_LAB.md)

รายงาน 4 หน้า ครอบคลุม:

### ✓ ตอบทุกคำถามในแลป:
- **ส่วน 1:** OLTP (guarded UPDATE, Idempotent, OLTP vs OLAP)
- **ส่วน 2:** Grain & Star Schema (Grain อธิบาย, Dimensions, Measures)
- **ส่วน 3:** OLAP Operations (Roll-up, Drill-up, Drill-down, Slice, Dice, HAVING, Drill-through)
- **ส่วน 4:** Pivot Table (SQL CASE, pandas pivot_table, margins, aggfunc test)
- **ส่วน 5:** Validation (UNION ALL, AOV vs AVG, FK Check, Additive measures)

### ✓ ข้อค้นพบ (2 ข้อ):
1. ยอดรายเดือนต่างกัน (690 vs 700)
2. AOV สูงกว่า AVG 33% เพราะลูกค้าซื้อเป็นชุด

### ✓ ข้อจำกัด (1 ข้อ):
- ข้อมูลไม่มี discount, tax, return

### ✓ ประกาศ AI:
- Prompt ที่ใช้
- จุดที่ตรวจแก้เอง (aggfunc test)

---

## 🔍 Checklist ก่อนส่ง

- [x] ทั้ง 12 SQL files (q01-q12.sql)
- [x] oltp_demo.py (รัน 2 รอบ)
- [x] pivot_student.py (P1-P4 complete)
- [x] ผลรัน TXT/CSV สำหรับแต่ละข้อ
- [x] pivot_province_month.csv (P1)
- [x] pivot_september.csv (P2)
- [x] REPORT_OLAP_LAB.md (4 หน้า)
- [x] Star Schema diagram (ในรายงาน)
- [x] ตอบคำถามทั้งหมด
- [x] ข้อค้นพบ 2 + ข้อจำกัด 1
- [x] ประกาศ AI + จุดแก้เอง
- [ ] ❌ .venv folder (ไม่ต้องส่ง)
- [ ] ❌ ฐานข้อมูล .db (ไม่ต้องส่ง)

---

## 📌 หมายเหตุ

- **ผลรันจริง** อาจแตกต่างจาก output files เล็กน้อย (ขึ้นอยู่เวลารัน)
- **วันที่เก็บการเปลี่ยนแปลง** อาจต่างจากตัวอย่างหากใช้ `lab.py --reset`
- **Pivot values** ควรจะเท่ากัน (ตรวจ assert ใน P3)

---

## 🎓 ส่งไปยัง

**รูปแบบไฟล์:** ZIP  
**ชื่อไฟล์:** `67160170_olap_lab.zip`  
**รายละเอียด:** ตามเอกสารให้มา

---

**ขอบคุณ!** 😊
