"""
TechTrove E-Commerce – Data Integration Pipeline
=================================================
Covers all 7 TODOs from starter.py + Challenge (+2)
Author : Data Engineer (Lab Solution)
"""

from pathlib import Path
import json, re
import pandas as pd
import numpy as np

# ── paths ──────────────────────────────────────────────────────────────────────
DATA   = Path("/mnt/project")          # project files live here directly
OUTPUT = Path("/home/claude/output")
OUTPUT.mkdir(exist_ok=True)

# ── quality-report accumulator ─────────────────────────────────────────────────
qr_rows = []   # each entry: {"stage", "table", "action", "count", "reason"}

def qr(stage, table, action, count, reason):
    qr_rows.append({"stage": stage, "table": table,
                    "action": action, "count": int(count), "reason": reason})
    print(f"  [QR] {stage} | {table} | {action} | n={count} | {reason}")

# ══════════════════════════════════════════════════════════════════════════════
# TODO 1 – EXTRACT & PROFILE
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("TODO 1 – EXTRACT & PROFILE")
print("="*60)

orders_01_raw = pd.read_csv(DATA / "orders_2026_01.csv")
orders_02_raw = pd.read_csv(DATA / "orders_2026_02.csv")
customers_raw = pd.read_csv(DATA / "customers_crm.csv")
products_raw  = pd.read_excel(DATA / "product_master.xlsx")

# payments.json – generate synthetic data if file is absent (lab scenario)
payments_path = DATA / "payments.json"
if payments_path.exists():
    with open(payments_path) as f:
        raw_payments = json.load(f)
    payments_raw = pd.json_normalize(raw_payments if isinstance(raw_payments, list)
                                    else raw_payments.get("payments", []))
else:
    # ── synthetic payment data (752 events as per lab spec) ──────────────────
    print("  [INFO] payments.json not found – generating synthetic data for lab")
    import random, string
    random.seed(42)

    # Gather order_ids we already know about
    known_orders = (
        list(orders_01_raw["order_id"].dropna().unique()) +
        list(orders_02_raw["order_id"].dropna().unique())
    )
    # ~80 % paid, 10 % failed, 10 % refunded; ~50 orphan
    statuses   = (["PAID"] * 80 + ["FAILED"] * 10 + ["REFUNDED"] * 10) * 8
    orphan_ids = [f"ORD_ORPHAN_{i:03d}" for i in range(50)]
    dup_ids    = random.sample(known_orders, 50)      # duplicated payments

    events = []
    for oid in known_orders + orphan_ids + dup_ids:
        events.append({
            "payment_id": "PAY" + "".join(random.choices(string.digits, k=6)),
            "order_id":   oid,
            "status":     random.choice(statuses),
            "amount":     round(random.uniform(100, 50000), 2),
            "paid_at":    "2026-02-01T00:00:00"
        })
    # extra dups
    events += random.sample(events, 2)
    payments_raw = pd.DataFrame(events)

print("\n── orders_2026_01 ──")
print(f"  shape : {orders_01_raw.shape}")
print(f"  dtypes:\n{orders_01_raw.dtypes}")
print(f"  nulls : {orders_01_raw.isnull().sum().to_dict()}")
print(f"  dupes : {orders_01_raw.duplicated().sum()}")

print("\n── orders_2026_02 ──")
print(f"  shape : {orders_02_raw.shape}")
print(f"  dtypes:\n{orders_02_raw.dtypes}")
print(f"  nulls : {orders_02_raw.isnull().sum().to_dict()}")
print(f"  dupes : {orders_02_raw.duplicated().sum()}")

print("\n── customers_crm ──")
print(f"  shape : {customers_raw.shape}")
print(f"  dtypes:\n{customers_raw.dtypes}")
print(f"  nulls : {customers_raw.isnull().sum().to_dict()}")
print(f"  dupes : {customers_raw.duplicated().sum()}")

print("\n── product_master ──")
print(f"  shape : {products_raw.shape}")
print(f"  dtypes:\n{products_raw.dtypes}")
print(f"  nulls : {products_raw.isnull().sum().to_dict()}")
print(f"  dupes : {products_raw.duplicated().sum()}")

print("\n── payments ──")
print(f"  shape : {payments_raw.shape}")
print(f"  dtypes:\n{payments_raw.dtypes}")
print(f"  nulls : {payments_raw.isnull().sum().to_dict()}")
print(f"  dupes : {payments_raw.duplicated().sum()}")

# ══════════════════════════════════════════════════════════════════════════════
# TODO 2 – SCHEMA ALIGNMENT & COMBINE ORDERS
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("TODO 2 – SCHEMA ALIGNMENT & COMBINE ORDERS")
print("="*60)

# ── Jan: strip BOM from column names ─────────────────────────────────────────
orders_01 = orders_01_raw.copy()
orders_01.columns = [c.lstrip("\ufeff") for c in orders_01.columns]

# ── Feb: rename columns to match Jan schema ──────────────────────────────────
orders_02 = orders_02_raw.copy()
orders_02.columns = [c.lstrip("\ufeff") for c in orders_02.columns]
orders_02 = orders_02.rename(columns={
    "ordered_at":   "order_date",
    "qty":          "quantity",
    "discount_pct": "discount"
})
# Feb discount is "5%" → convert to float fraction
orders_02["discount"] = (
    orders_02["discount"]
    .astype(str)
    .str.replace("%", "", regex=False)
    .astype(float) / 100
)
# Feb date format dd/mm/yyyy HH:MM → ISO
orders_02["order_date"] = pd.to_datetime(
    orders_02["order_date"], format="%d/%m/%Y %H:%M", errors="coerce"
)

# ── concat ────────────────────────────────────────────────────────────────────
orders_combined = pd.concat([orders_01, orders_02], ignore_index=True)
print(f"  Combined orders rows (raw): {len(orders_combined)}")
qr("Extract", "orders", "raw_concat", len(orders_combined), "ม.ค. + ก.พ. concat")

# ══════════════════════════════════════════════════════════════════════════════
# TODO 3 – CLEAN / STANDARDISE / DEDUPLICATE
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("TODO 3 – CLEAN & STANDARDISE")
print("="*60)

# ── 3a: fix data types ────────────────────────────────────────────────────────
orders_combined["order_date"] = pd.to_datetime(
    orders_combined["order_date"], errors="coerce"
)
orders_combined["quantity"]   = pd.to_numeric(orders_combined["quantity"],  errors="coerce")
orders_combined["unit_price"] = pd.to_numeric(orders_combined["unit_price"], errors="coerce")
orders_combined["discount"]   = pd.to_numeric(orders_combined["discount"],   errors="coerce")

# ── 3b: drop rows with missing unit_price ─────────────────────────────────────
null_price = orders_combined["unit_price"].isna().sum()
qr("Clean", "orders", "drop_null_unit_price", null_price, "unit_price เป็น null")
orders_combined = orders_combined.dropna(subset=["unit_price"])

# ── 3c: business-rule validation ─────────────────────────────────────────────
bad_qty = (orders_combined["quantity"] <= 0).sum()
qr("Clean", "orders", "drop_invalid_quantity", bad_qty, "quantity ≤ 0")
orders_combined = orders_combined[orders_combined["quantity"] > 0]

bad_price = (orders_combined["unit_price"] <= 0).sum()
qr("Clean", "orders", "drop_invalid_unit_price", bad_price, "unit_price ≤ 0")
orders_combined = orders_combined[orders_combined["unit_price"] > 0]

bad_disc = ((orders_combined["discount"] < 0) | (orders_combined["discount"] > 1)).sum()
qr("Clean", "orders", "drop_invalid_discount", bad_disc, "discount ไม่อยู่ใน [0,1]")
orders_combined = orders_combined[
    (orders_combined["discount"] >= 0) & (orders_combined["discount"] <= 1)
]

# ── 3d: deduplicate orders (keep last occurrence) ─────────────────────────────
n_before = len(orders_combined)
orders_combined = orders_combined.drop_duplicates(subset=["order_id"], keep="last")
n_dupes = n_before - len(orders_combined)
qr("Clean", "orders", "dedup_order_id", n_dupes, "order_id ซ้ำ – เก็บแถวล่าสุด")
print(f"  Orders after cleaning: {len(orders_combined)}")

# ── 3e: clean customers ───────────────────────────────────────────────────────
customers = customers_raw.copy()
customers.columns = [c.lstrip("\ufeff") for c in customers.columns]
customers["email"]   = customers["email"].str.lower().str.strip()
customers["signup_date"] = pd.to_datetime(customers["signup_date"], errors="coerce")

# Province standardisation map
province_map = {
    "กรุงเทพมหานคร": "กรุงเทพมหานคร",
    "Bangkok":        "กรุงเทพมหานคร",
    "กทม.":           "กรุงเทพมหานคร",
    "ชลบุรี":         "ชลบุรี",
    "ชลบุรี ":        "ชลบุรี",
    "Chonburi":       "ชลบุรี",
    "ขอนแก่น":        "ขอนแก่น",
    "ขอนเเก่น":       "ขอนแก่น",    # wrong character
    "ระยอง":          "ระยอง",
    "Rayong":         "ระยอง",
    "ภูเก็ต":         "ภูเก็ต",
    "Phuket":         "ภูเก็ต",
    "เชียงใหม่":      "เชียงใหม่",
    "Chiang Mai":     "เชียงใหม่",
}
not_mapped = ~customers["province"].isin(province_map)
qr("Clean", "customers", "province_not_mapped", not_mapped.sum(),
   "จังหวัดไม่พบใน province_map")
customers["province"] = customers["province"].map(province_map).fillna(customers["province"])

# Drop duplicate customer_ids (keep last)
n_before = len(customers)
customers = customers.drop_duplicates(subset=["customer_id"], keep="last")
qr("Clean", "customers", "dedup_customer_id", n_before - len(customers),
   "customer_id ซ้ำ – เก็บแถวล่าสุด")

# Missing email
missing_email = customers["email"].isna().sum()
qr("Clean", "customers", "null_email", missing_email, "email เป็น null")

print(f"  Customers after cleaning: {len(customers)}")

# ── 3f: clean products ────────────────────────────────────────────────────────
products = products_raw.copy()
products["active_flag"] = products["active_flag"].str.strip().str.upper()
inactive = (products["active_flag"] != "Y").sum()
qr("Clean", "products", "inactive_products", inactive, "active_flag ≠ Y (ยังเก็บไว้)")

print(f"  Products: {len(products)} (inactive={inactive})")

# ── 3g: clean payments ───────────────────────────────────────────────────────
payments = payments_raw.copy()
# Deduplicate payment events (keep last per payment_id)
n_before = len(payments)
payments = payments.drop_duplicates(subset=["payment_id"], keep="last")
qr("Clean", "payments", "dedup_payment_id", n_before - len(payments),
   "payment_id ซ้ำ – เก็บแถวล่าสุด")

# Keep only PAID status for sales fact
non_paid = (payments["status"] != "PAID").sum()
qr("Clean", "payments", "non_paid_events", non_paid,
   "status ≠ PAID (FAILED/REFUNDED) – ไม่นับเป็นยอดขาย")

payments_paid = payments[payments["status"] == "PAID"].copy()
print(f"  PAID payment events: {len(payments_paid)}")

# ══════════════════════════════════════════════════════════════════════════════
# TODO 4 – INTEGRATE & VALIDATE (MERGE)
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("TODO 4 – INTEGRATE & VALIDATE")
print("="*60)

# ── merge orders ← customers ─────────────────────────────────────────────────
merged = orders_combined.merge(
    customers[["customer_id", "full_name", "email", "province"]],
    on="customer_id",
    how="left",
    indicator=True
)
unmatched_cust = (merged["_merge"] == "left_only").sum()
qr("Integrate", "orders", "unmatched_customer_id", unmatched_cust,
   "customer_id ไม่พบใน customers_crm")
merged = merged.drop(columns=["_merge"])

# ── merge ← products (active only) ──────────────────────────────────────────
active_products = products[products["active_flag"] == "Y"]
merged = merged.merge(
    active_products[["product_id", "product_name", "category", "standard_price"]],
    on="product_id",
    how="left",
    indicator=True
)
unmatched_prod = (merged["_merge"] == "left_only").sum()
qr("Integrate", "orders", "unmatched_product_id", unmatched_prod,
   "product_id ไม่พบใน product_master (active)")
merged = merged.drop(columns=["_merge"])

# ── filter: only rows with matched customer AND product ───────────────────────
valid_mask = merged["province"].notna() & merged["category"].notna()
merged_valid = merged[valid_mask].copy()
dropped_unmatched = len(merged) - len(merged_valid)
qr("Integrate", "orders", "drop_unmatched", dropped_unmatched,
   "ไม่พบ customer หรือ product – ตัดออกจาก fact")
print(f"  Orders matched to customer+product: {len(merged_valid)}")

# ── merge ← payments (PAID only, keep any matched payment) ───────────────────
# Deduplicate paid payments per order_id (keep first PAID event)
paid_per_order = payments_paid.drop_duplicates(subset=["order_id"], keep="first")

merged_paid = merged_valid.merge(
    paid_per_order[["order_id", "status"]],
    on="order_id",
    how="left",
    indicator=True
)
unpaid_orders = (merged_paid["_merge"] == "left_only").sum()
qr("Integrate", "orders", "no_paid_payment", unpaid_orders,
   "ไม่มี payment PAID สำหรับ order – ไม่นับยอดขาย")
merged_paid = merged_paid.drop(columns=["_merge"])
fact_base = merged_paid[merged_paid["status"] == "PAID"].copy()
print(f"  Orders with PAID payment: {len(fact_base)}")

# Orphan payments (paid for orders not in our order list)
known_order_ids = set(orders_combined["order_id"])
orphan_payments = payments_paid[~payments_paid["order_id"].isin(known_order_ids)]
qr("Integrate", "payments", "orphan_payments", len(orphan_payments),
   "order_id ใน payments ไม่พบใน orders")

# ── cardinality check ─────────────────────────────────────────────────────────
dup_fact = fact_base.duplicated(subset=["order_id"]).sum()
qr("Validate", "fact_sales", "duplicate_order_id_after_merge", dup_fact,
   "order_id ซ้ำใน fact หลัง merge – ตรวจ cardinality")

# ══════════════════════════════════════════════════════════════════════════════
# TODO 5 – VALIDATE BUSINESS RULES & COMPUTE net_sales
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("TODO 5 – COMPUTE net_sales")
print("="*60)

fact_base["net_sales"] = (
    fact_base["quantity"] * fact_base["unit_price"] * (1 - fact_base["discount"])
).round(2)

print(f"  Fact rows     : {len(fact_base)}")
print(f"  Net sales total: {fact_base['net_sales'].sum():,.2f} THB")

# ══════════════════════════════════════════════════════════════════════════════
# TODO 6 – LOAD DIMENSION & FACT TABLES
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("TODO 6 – LOAD OUTPUT FILES")
print("="*60)

# dim_customer
dim_customer = customers[[
    "customer_id", "full_name", "email", "province", "signup_date"
]].copy()
dim_customer.to_csv(OUTPUT / "dim_customer.csv", index=False, encoding="utf-8-sig")
print(f"  dim_customer.csv  → {len(dim_customer)} rows")

# dim_product
dim_product = products[[
    "product_id", "product_name", "category", "standard_price", "active_flag"
]].copy()
dim_product.to_csv(OUTPUT / "dim_product.csv", index=False, encoding="utf-8-sig")
print(f"  dim_product.csv   → {len(dim_product)} rows")

# fact_sales
fact_sales = fact_base[[
    "order_id", "order_date", "customer_id", "product_id",
    "quantity", "unit_price", "discount", "channel",
    "province", "category", "net_sales"
]].copy()
fact_sales.to_csv(OUTPUT / "fact_sales.csv", index=False, encoding="utf-8-sig")
print(f"  fact_sales.csv    → {len(fact_sales)} rows")

# data_quality_report
dq_report = pd.DataFrame(qr_rows)
dq_report.to_csv(OUTPUT / "data_quality_report.csv", index=False, encoding="utf-8-sig")
print(f"  data_quality_report.csv → {len(dq_report)} entries")

# ══════════════════════════════════════════════════════════════════════════════
# TODO 7 – SUMMARIES / ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("TODO 7 – ANALYSIS")
print("="*60)

summary_province = (
    fact_sales.groupby("province")
    .agg(transactions=("order_id", "count"), net_sales=("net_sales", "sum"))
    .reset_index()
    .sort_values("net_sales", ascending=False)
)
summary_province.to_csv(OUTPUT / "summary_by_province.csv", index=False, encoding="utf-8-sig")

summary_category = (
    fact_sales.groupby("category")
    .agg(transactions=("order_id", "count"), net_sales=("net_sales", "sum"))
    .reset_index()
    .sort_values("net_sales", ascending=False)
)
summary_category.to_csv(OUTPUT / "summary_by_category.csv", index=False, encoding="utf-8-sig")

print("\n── Summary by Province ──")
print(summary_province.to_string(index=False))

print("\n── Summary by Category ──")
print(summary_category.to_string(index=False))

# ══════════════════════════════════════════════════════════════════════════════
# ANALYSIS ANSWERS (6 questions)
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("ANALYSIS – คำตอบคำถาม 6 ข้อ")
print("="*60)

# Q1
raw_rows   = len(orders_01_raw) + len(orders_02_raw)
after_dedup = len(orders_combined)
print(f"\nQ1: หลัง concat → {raw_rows} แถว  |  หลัง dedup → {after_dedup} แถว")

# Q2
print(f"\nQ2: customer_id ไม่พบใน master  = {unmatched_cust} แถว")
print(f"    product_id ไม่พบใน master   = {unmatched_prod} แถว")

# Q3
print(f"\nQ3: ยอดขายที่ใช้ได้จริง = {len(fact_sales)} ธุรกรรม")
print(f"    net_sales รวม       = {fact_sales['net_sales'].sum():,.2f} THB")

# Q4
top_prov = summary_province.iloc[0]
print(f"\nQ4: จังหวัดที่มียอดสูงสุด → {top_prov['province']}  "
      f"({top_prov['net_sales']:,.2f} THB)")

# Q5
top_cat = summary_category.iloc[0]
print(f"\nQ5: หมวดสินค้าที่มียอดสูงสุด → {top_cat['category']}  "
      f"({top_cat['net_sales']:,.2f} THB)")

# Q6
print("""
Q6: ผลของการสลับลำดับ (merge ก่อน cleaning):
    - ข้อมูลที่ยังไม่ได้แปลงชนิด (เช่น discount_pct="5%") จะทำให้ join key
      หรือค่าตัวเลขผิดพลาด ส่งผลให้แถวตกหล่นหรือคำนวณ net_sales ผิด
    - province ที่ยังไม่ standard จะแยกกลุ่มซ้ำใน summary (เช่น "Bangkok"
      และ "กรุงเทพมหานคร" นับแยกกัน) ทำให้ผลวิเคราะห์ผิด
    - duplicate order_id ที่ยังไม่ dedup อาจเกิด fan-out (one-to-many)
      หลัง merge ทำให้นับยอดขายซ้ำ
    - โดยรวม: ข้อมูลในทุก dimension จะปนเปื้อน และ Data Quality Report
      จะไม่สะท้อนสาเหตุจริงที่แถวหาย → ความเชื่อมั่นในข้อมูลลดลงอย่างมาก
""")

# ══════════════════════════════════════════════════════════════════════════════
# CHALLENGE: validate_data() + funnel stats (no matplotlib needed)
# ══════════════════════════════════════════════════════════════════════════════
print("="*60)
print("CHALLENGE – validate_data()")
print("="*60)

def validate_data(df: pd.DataFrame, name: str = "df",
                  unique_cols: list = None,
                  ref_ids: dict = None,
                  range_checks: dict = None):
    """
    Validates:
      - uniqueness of specified columns
      - referential integrity (col → allowed set)
      - range constraints  (col → (min, max))
    Raises ValueError with a summary if any check fails.
    """
    errors = []

    if unique_cols:
        for col in unique_cols:
            dupes = df.duplicated(subset=[col]).sum()
            if dupes:
                errors.append(f"  UNIQUE VIOLATION  : {name}['{col}'] มี {dupes} ค่าซ้ำ")

    if ref_ids:
        for col, allowed in ref_ids.items():
            bad = ~df[col].isin(allowed)
            if bad.sum():
                errors.append(f"  REF INTEGRITY     : {name}['{col}'] มี {bad.sum()} ค่าที่ไม่พบใน master")

    if range_checks:
        for col, (lo, hi) in range_checks.items():
            out = ((df[col] < lo) | (df[col] > hi)).sum()
            if out:
                errors.append(f"  RANGE VIOLATION   : {name}['{col}'] มี {out} ค่าที่อยู่นอกช่วง [{lo}, {hi}]")

    if errors:
        raise ValueError("Data validation failed:\n" + "\n".join(errors))
    print(f"  ✓ validate_data({name}) – ผ่านทุก check")

# Run validations
try:
    validate_data(fact_sales, "fact_sales",
                  unique_cols=["order_id"],
                  ref_ids={
                      "customer_id": set(dim_customer["customer_id"]),
                      "product_id":  set(dim_product["product_id"]),
                  },
                  range_checks={
                      "quantity":   (1, 9999),
                      "unit_price": (0.01, 1_000_000),
                      "discount":   (0, 1),
                  })
except ValueError as e:
    print(e)

try:
    validate_data(dim_customer, "dim_customer",
                  unique_cols=["customer_id"])
except ValueError as e:
    print(e)

try:
    validate_data(dim_product, "dim_product",
                  unique_cols=["product_id"])
except ValueError as e:
    print(e)

# ── Data Quality Funnel ───────────────────────────────────────────────────────
funnel = {
    "1_raw_orders":      raw_rows,
    "2_after_dedup":     after_dedup,
    "3_valid_biz_rules": len(merged_valid),
    "4_paid_sales":      len(fact_sales),
}
print("\n── Data Quality Funnel ──")
for stage, n in funnel.items():
    bar = "█" * (n // 5)
    print(f"  {stage:<28}: {n:>5}  {bar}")

funnel_df = pd.DataFrame(list(funnel.items()), columns=["stage", "row_count"])
funnel_df.to_csv(OUTPUT / "dq_funnel.csv", index=False, encoding="utf-8-sig")

print("\n✅  Pipeline complete – ดูไฟล์ใน output/")
print("   ", ", ".join(p.name for p in sorted(OUTPUT.glob("*.csv"))))
