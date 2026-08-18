# Week 7 — Python Data Pipeline Engineering

งานนี้สร้างคลังข้อมูลค้าปลีกบน SQLite จากไฟล์ Excel ที่ได้รับ โดยรองรับการโหลดข้อมูลแบบ Incremental และ Idempotent ไฟล์ต้นฉบับจะถูกอ่านอย่างเดียวและไม่มีการแก้ไข

## ไฟล์ที่ส่ง

- `pipeline.py` — โค้ดสำหรับ Extract, Transform, Data Quality, Load, Logging และ Orchestration
- `retail_dw.db` — ฐานข้อมูล SQLite ที่สร้าง Star Schema และโหลดครบทุก batch
- `quarantine.csv` — ข้อมูลทุกแถวที่ไม่ผ่านการตรวจสอบ พร้อม `reason_code`
- `pipeline_run_log.csv` และตาราง `pipeline_run_log` — ประวัติและตัวชี้วัดของการรันแต่ละครั้ง

## วิธีรัน

```powershell
python pipeline.py --acceptance-sequence
```

คำสั่งข้างต้นจะรันตามลำดับการทดสอบที่กำหนด คือ `batch_1 → batch_1 ซ้ำ → batch_2 → batch_3` โดยค่าเริ่มต้นของ input คือไฟล์ Excel ที่ได้รับในโฟลเดอร์ Downloads หากต้องการระบุไฟล์ที่เข้ากันได้ไฟล์อื่น ให้ใช้ `--input "path\to\workbook.xlsx"` การรันปกติที่ไม่ใช้ `--acceptance-sequence` จะโหลด batch 1–3 อย่างละหนึ่งครั้ง

## ผลการวิเคราะห์ชุดข้อมูลจริง

Workbook มีชีต `customers` 180 แถว, `products` 48 แถว และ `orders_batch_1`, `orders_batch_2`, `orders_batch_3` จำนวน 420, 424 และ 424 แถวตามลำดับ คอลัมน์ของคำสั่งซื้อมี `order_id`, `order_datetime`, `customer_id`, `product_id`, `quantity`, `unit_price`, `discount_pct`, `payment_method`, `sales_channel`, `updated_at` และ `source_batch`

ข้อมูลจำนวนและราคาในไฟล์ถูกอ่านเป็น object ก่อน แล้วแปลงด้วย `pd.to_numeric(errors="coerce")`; วันเวลาถูกแปลงด้วย `pd.to_datetime(errors="coerce")` จึงรองรับค่าข้อความหรือค่าผิดรูปแบบที่ตั้งใจให้มีใน source ได้ โดยไม่ต้องแก้ Excel

## การแปลงและกฎตรวจสอบคุณภาพข้อมูล

`payment_method` ถูก normalize แบบไม่สนตัวพิมพ์เล็กใหญ่เป็น `CASH`, `CREDIT_CARD`, `BANK_TRANSFER`, `PROMPTPAY` หรือ `E_WALLET` ส่วน `sales_channel` ถูก normalize เป็น `STORE`, `ONLINE` หรือ `MARKETPLACE` ค่าไม่อยู่ใน mapping หรือค่าว่างจะถูกส่งไป quarantine

Pipeline ตรวจสอบ `order_id`, วันเวลาของรายการและการปรับปรุงข้อมูล, `quantity > 0`, `unit_price > 0`, `discount_pct` อยู่ระหว่าง 0–100 และตรวจว่า `customer_id`/`product_id` มีอยู่จริงใน dimension table แถวที่มีปัญหาจะถูกบันทึกเป็น `reason_code` เดียวตามลำดับความสำคัญของกฎ เพื่อให้ตรวจสอบย้อนหลังได้ชัดเจน

หลังผ่านกฎพื้นฐาน ระบบจะ deduplicate ด้วย `order_id` โดยเก็บแถวที่มี `updated_at` ล่าสุดไว้ แถวที่เก่ากว่าจะเข้าสู่ quarantine ด้วยรหัส `DUPLICATE_ORDER_ID_SUPERSEDED` จากนั้นคำนวณ `gross_amount = quantity × unit_price` และ `net_amount = gross_amount × (1 − discount_pct/100)`

## Star Schema และระดับข้อมูลของ Fact

ฐานข้อมูลมีตาราง dimension คือ `dim_customer(customer_key, customer_id, …)`, `dim_product(product_key, product_id, …)` และ `dim_date(date_key, full_date, …)` พร้อมตาราง `fact_sales` นอกจากนี้มีตารางตรวจสอบคือ `pipeline_run_log` และ `quarantine_records`

ระดับข้อมูล (grain) ของ `fact_sales` คือ **หนึ่งรายการขายที่ผ่านการตรวจสอบและเป็นเวอร์ชันล่าสุดต่อหนึ่ง `order_id`** โดย `order_id` เป็น primary key ของ fact และ dimension key ทั้งสามเป็น foreign key

## Incremental Loading และ Idempotency

การโหลดแต่ละครั้งทำภายใน SQLite transaction เดียว Dimension ใช้ upsert, ตารางวันที่ใช้ insert-or-ignore และ fact ใช้ upsert ที่ update เฉพาะข้อมูลขาเข้าซึ่งมี `updated_at` ใหม่กว่าเท่านั้น ดังนั้นการรัน batch เดิมซ้ำจะไม่เพิ่มหรือคูณยอดขายซ้ำ

ระบบเก็บ `watermark_before` และ `watermark_after` ซึ่งเป็น `updated_at` สูงสุดใน fact table ของแต่ละรอบ การตรวจสอบ `updated_at` ในคำสั่ง upsert เป็นกลไกหลักที่ป้องกันข้อมูลเวอร์ชันเก่ามาทับข้อมูลใหม่ แม้เป็นข้อมูลที่เข้ามาล่าช้า

ความหมายของตัวชี้วัดคือ `rows_read = rows_valid + rows_rejected`; `rows_duplicate` เป็นส่วนหนึ่งของ `rows_rejected`; และ `rows_loaded` นับเฉพาะ insert/update ที่เปลี่ยนข้อมูลจริง จึงเป็น 0 ได้เมื่อรัน batch เดิมซ้ำ

## Acceptance Tests

ฟังก์ชัน `acceptance_tests()` ตรวจสอบว่า `order_id` ใน fact ไม่ซ้ำ, fact ทุกแถวเชื่อมกับ dimension ได้ครบ, ไม่มี quantity/unit price/net amount ที่ผิดเงื่อนไข และทุกแถวใน quarantine มี `reason_code`

## Reflection

Availability มีความสำคัญพอ ๆ กับความเข้มงวดใน production pipeline เพราะข้อมูลต้นทางที่ผิดเพียงหนึ่งแถวไม่ควรหยุดรายงานทั้งหมด การแยกข้อมูลผิดไป quarantine ช่วยให้ข้อมูลที่ถูกต้องยังเข้าสู่คลังข้อมูลได้ตามเวลา และยังเก็บหลักฐานไว้แก้ไขภายหลัง ขณะเดียวกัน validation ที่เข้มงวดยังคุ้มครองรายงานจากจำนวน ราคา หรือความสัมพันธ์ที่ผิดพลาด Run log, สถานะการรัน และ watermark ทำให้การทำงานตรวจสอบย้อนกลับและเริ่มใหม่ได้ Idempotent upsert ป้องกันการรันซ้ำหรือการส่งข้อมูลซ้ำจากการนับรายได้ซ้ำ เมื่อรวมกันแล้ว กลไกเหล่านี้ช่วยเปลี่ยนปัญหาจากต้นทางให้เป็นงานที่วัดผลและแก้ไขได้ แทนที่จะทำให้คลังข้อมูลหยุดให้บริการ
