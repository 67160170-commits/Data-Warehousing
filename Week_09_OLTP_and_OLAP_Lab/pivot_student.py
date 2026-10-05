from pathlib import Path
import sqlite3
import pandas as pd
ROOT=Path(__file__).resolve().parent

# โหลดข้อมูลจาก warehouse.db
with sqlite3.connect((ROOT/'data'/'warehouse.db').as_uri()+'?mode=ro',uri=True) as con:
    df=pd.read_sql_query('SELECT * FROM sales',con)

print("=" * 60)
print("DATA LOADED")
print("=" * 60)
print(f"Shape: {df.shape}")
print(df.head())

# ====== P1: Province x Month Pivot with Margins ======
print("\n" + "=" * 60)
print("P1: PROVINCE x MONTH (sum, fill_value=0, margins=True)")
print("=" * 60)
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
print(p1)
p1.to_csv(ROOT/'pivot_province_month.csv')
print("✓ Saved: pivot_province_month.csv")

# ====== P2: Filter September then Category x Province ======
print("\n" + "=" * 60)
print("P2: SEPTEMBER ONLY - CATEGORY x PROVINCE")
print("=" * 60)
df_sep = df[df['month'] == '2026-09']
print(f"Rows after filter: {len(df_sep)}")
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
print(p2)
p2.to_csv(ROOT/'pivot_september.csv')
print("✓ Saved: pivot_september.csv")

# ====== P3: Assert Grand Total ======
print("\n" + "=" * 60)
print("P3: ASSERT GRAND TOTAL")
print("=" * 60)
grand_total_p1 = p1.loc['Total', 'Total']
df_total = df['amount'].sum()
print(f"Grand Total from P1 pivot: {grand_total_p1}")
print(f"Sum from df['amount']:     {df_total}")
try:
    assert grand_total_p1 == df_total, f"MISMATCH: {grand_total_p1} != {df_total}"
    print("✓ ASSERT PASSED!")
except AssertionError as e:
    print(f"✗ ASSERT FAILED: {e}")

# ====== P4: Test Aggfunc - ลบ aggfunc ดู (default = mean) ======
print("\n" + "=" * 60)
print("P4: TEST - ลบ aggfunc (default = mean)")
print("=" * 60)
p_mean = pd.pivot_table(
    df,
    index='province',
    columns='month',
    values='amount',
    fill_value=0,
    margins=True,
    margins_name='Total'
)
print(p_mean)
print("\nTesting Bangkok September:")
if 'Bangkok' in p_mean.index and '2026-09' in p_mean.columns:
    val = p_mean.loc['Bangkok', '2026-09']
    print(f"  Value: {val}")
    print(f"  Explanation: ค่านี้คือ MEAN (เฉลี่ย) ของยอดขาย ไม่ใช่ SUM")
    print(f"  ที่แตกต่างจาก P1 ที่ใช้ sum ตามโจทย์")

# ====== Drink Filter (หากมีแยก Drink) ======
print("\n" + "=" * 60)
print("BONUS: DRINK ONLY (สำหรับคำถามท้ายแลป)")
print("=" * 60)
df_drink = df[df['category'] == 'Drink']
print(f"Drink rows: {len(df_drink)}")
print(f"Drink revenue: {df_drink['amount'].sum()} บาท")
p_drink = pd.pivot_table(
    df_drink,
    index='province',
    columns='month',
    values='amount',
    aggfunc='sum',
    fill_value=0,
    margins=True,
    margins_name='Total'
)
print(p_drink)
print("✓ Saved as reference (not required)")

print("\n" + "=" * 60)
print("COMPLETED ALL PIVOTS")
print("=" * 60)
