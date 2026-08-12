import json
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "data" / "warehouse" / "warehouse.db"

def validate(transformed):
    source_valid_rows = len(transformed["fact_sales"])
    source_total_sales = round(float(transformed["fact_sales"]["sales_amount"].sum()), 2)

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    warehouse_rows = cur.execute("SELECT COUNT(*) FROM fact_sales").fetchone()[0]
    duplicate_order_ids = cur.execute(
        """SELECT COUNT(*) FROM (
             SELECT order_id FROM fact_sales
             GROUP BY order_id HAVING COUNT(*) > 1
        )"""
    ).fetchone()[0]
    warehouse_total_sales = round(
        float(cur.execute("SELECT COALESCE(SUM(sales_amount), 0) FROM fact_sales").fetchone()[0]), 2
    )
    con.close()

    status = "PASS" if (
        source_valid_rows == warehouse_rows
        and duplicate_order_ids == 0
        and source_total_sales == warehouse_total_sales
    ) else "FAIL"

    result = {
        "source_valid_rows": source_valid_rows,
        "warehouse_rows": warehouse_rows,
        "duplicate_order_ids": duplicate_order_ids,
        "source_total_sales": source_total_sales,
        "warehouse_total_sales": warehouse_total_sales,
        "status": status,
    }

    with open(BASE_DIR / "output" / "validation.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result
