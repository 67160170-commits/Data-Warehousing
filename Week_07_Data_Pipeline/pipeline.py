"""Incremental, idempotent ETL pipeline for the Week 7 retail lab.

The source workbook is read only.  Run this module directly to execute the
required acceptance sequence: batch 1, batch 1 again, batch 2, then batch 3.
"""
from __future__ import annotations

import argparse
import csv
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class PipelineConfig:
    input_path: Path
    output_db: Path = Path("retail_dw.db")
    quarantine_path: Path = Path("quarantine.csv")
    run_log_path: Path = Path("pipeline_run_log.csv")
    batches: tuple[int, ...] = (1, 2, 3)
    error_mode: str = "quarantine"  # quarantine (continue) or raise
    payment_mapping: dict[str, str] = field(default_factory=lambda: {
        "cash": "CASH", "credit card": "CREDIT_CARD", "bank transfer": "BANK_TRANSFER",
        "promptpay": "PROMPTPAY", "e-wallet": "E_WALLET",
    })
    channel_mapping: dict[str, str] = field(default_factory=lambda: {
        "store": "STORE", "online": "ONLINE", "marketplace": "MARKETPLACE",
    })


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS dim_customer (
        customer_key INTEGER PRIMARY KEY,
        customer_id TEXT NOT NULL UNIQUE,
        customer_name TEXT NOT NULL, province TEXT NOT NULL, segment TEXT NOT NULL,
        signup_date TEXT
    );
    CREATE TABLE IF NOT EXISTS dim_product (
        product_key INTEGER PRIMARY KEY,
        product_id TEXT NOT NULL UNIQUE,
        product_name TEXT NOT NULL, category TEXT NOT NULL,
        reference_unit_price REAL NOT NULL, active_flag TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS dim_date (
        date_key INTEGER PRIMARY KEY,
        full_date TEXT NOT NULL UNIQUE, day INTEGER NOT NULL, month INTEGER NOT NULL,
        quarter INTEGER NOT NULL, year INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS fact_sales (
        order_id TEXT PRIMARY KEY,
        date_key INTEGER NOT NULL REFERENCES dim_date(date_key),
        customer_key INTEGER NOT NULL REFERENCES dim_customer(customer_key),
        product_key INTEGER NOT NULL REFERENCES dim_product(product_key),
        quantity REAL NOT NULL CHECK(quantity > 0),
        unit_price REAL NOT NULL CHECK(unit_price > 0),
        discount_pct REAL NOT NULL CHECK(discount_pct BETWEEN 0 AND 100),
        gross_amount REAL NOT NULL CHECK(gross_amount >= 0),
        net_amount REAL NOT NULL CHECK(net_amount >= 0),
        payment_method TEXT NOT NULL, sales_channel TEXT NOT NULL,
        updated_at TEXT NOT NULL, source_batch INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS pipeline_run_log (
        run_id TEXT PRIMARY KEY, batch_name TEXT NOT NULL, started_at TEXT NOT NULL,
        ended_at TEXT, rows_read INTEGER NOT NULL DEFAULT 0, rows_valid INTEGER NOT NULL DEFAULT 0,
        rows_rejected INTEGER NOT NULL DEFAULT 0, rows_duplicate INTEGER NOT NULL DEFAULT 0,
        rows_loaded INTEGER NOT NULL DEFAULT 0, watermark_before TEXT, watermark_after TEXT,
        status TEXT NOT NULL, error_message TEXT
    );
    CREATE TABLE IF NOT EXISTS quarantine_records (
        quarantine_id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, source_batch INTEGER,
        order_id TEXT, reason_code TEXT NOT NULL, raw_record TEXT NOT NULL, quarantined_at TEXT NOT NULL
    );
    """)


def extract(config: PipelineConfig, batch: int) -> pd.DataFrame:
    """Extract one source sheet; errors surface to orchestration and get logged."""
    sheet = f"orders_batch_{batch}"
    try:
        df = pd.read_excel(config.input_path, sheet_name=sheet, dtype=object)
        logging.info("Extracted %s: %d rows", sheet, len(df))
        return df
    except Exception:
        logging.exception("Extraction failed for %s", sheet)
        raise


def normalize(value: object, mapping: dict[str, str]) -> object:
    if pd.isna(value):
        return pd.NA
    return mapping.get(str(value).strip().casefold(), pd.NA)


def validate_transform(raw: pd.DataFrame, config: PipelineConfig, customer_ids: set[str], product_ids: set[str]) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """Coerce types, validate DQ/FK rules, and return clean + quarantined rows.

    Exactly one reason_code is retained: the first applicable reason in the
    documented priority order.  Duplicate rows are quarantined after all basic
    validations; the row with the greatest updated_at per order_id is retained.
    """
    df = raw.copy()
    for col in ("quantity", "unit_price", "discount_pct"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ("order_datetime", "updated_at"):
        df[col] = pd.to_datetime(df[col], errors="coerce")
    df["payment_method"] = df["payment_method"].map(lambda x: normalize(x, config.payment_mapping))
    df["sales_channel"] = df["sales_channel"].map(lambda x: normalize(x, config.channel_mapping))
    df["reason_code"] = pd.NA

    rules = [
        (df["order_id"].isna() | (df["order_id"].astype(str).str.strip() == ""), "MISSING_ORDER_ID"),
        (df["order_datetime"].isna(), "INVALID_ORDER_DATETIME"),
        (df["updated_at"].isna(), "INVALID_UPDATED_AT"),
        (df["quantity"].isna() | (df["quantity"] <= 0), "INVALID_QUANTITY"),
        (df["unit_price"].isna() | (df["unit_price"] <= 0), "INVALID_UNIT_PRICE"),
        (df["discount_pct"].isna() | ~df["discount_pct"].between(0, 100), "INVALID_DISCOUNT_PCT"),
        (~df["customer_id"].isin(customer_ids), "INVALID_CUSTOMER_FK"),
        (~df["product_id"].isin(product_ids), "INVALID_PRODUCT_FK"),
        (df["payment_method"].isna(), "INVALID_PAYMENT_METHOD"),
        (df["sales_channel"].isna(), "INVALID_SALES_CHANNEL"),
    ]
    for mask, code in rules:
        df.loc[df["reason_code"].isna() & mask, "reason_code"] = code
    base_clean = df[df["reason_code"].isna()].copy()
    # stable ordering means tied timestamps retain their first source occurrence
    base_clean = base_clean.sort_values(["order_id", "updated_at"], kind="mergesort")
    duplicate_mask = base_clean.duplicated("order_id", keep="last")
    base_clean.loc[duplicate_mask, "reason_code"] = "DUPLICATE_ORDER_ID_SUPERSEDED"
    df.loc[base_clean.index, "reason_code"] = base_clean["reason_code"]
    duplicates = int(duplicate_mask.sum())
    clean = df[df["reason_code"].isna()].copy()
    rejected = df[df["reason_code"].notna()].copy()
    clean["gross_amount"] = (clean["quantity"] * clean["unit_price"]).round(2)
    clean["net_amount"] = (clean["gross_amount"] * (1 - clean["discount_pct"] / 100)).round(2)
    return clean, rejected, duplicates


def seed_dimensions(conn: sqlite3.Connection, config: PipelineConfig) -> None:
    customers = pd.read_excel(config.input_path, sheet_name="customers", dtype=object)
    products = pd.read_excel(config.input_path, sheet_name="products", dtype=object)
    conn.executemany("""INSERT INTO dim_customer(customer_id, customer_name, province, segment, signup_date)
        VALUES(?,?,?,?,?) ON CONFLICT(customer_id) DO UPDATE SET customer_name=excluded.customer_name,
        province=excluded.province, segment=excluded.segment, signup_date=excluded.signup_date""", customers.fillna("").itertuples(index=False, name=None))
    product_rows = []
    for r in products.fillna("").itertuples(index=False):
        price = float(r.unit_price)
        product_rows.append((r.product_id, r.product_name, r.category, price, r.active_flag))
    conn.executemany("""INSERT INTO dim_product(product_id, product_name, category, reference_unit_price, active_flag)
        VALUES(?,?,?,?,?) ON CONFLICT(product_id) DO UPDATE SET product_name=excluded.product_name,
        category=excluded.category, reference_unit_price=excluded.reference_unit_price, active_flag=excluded.active_flag""", product_rows)


def append_quarantine(conn: sqlite3.Connection, path: Path, rejected: pd.DataFrame, run_id: str, batch: int) -> None:
    if rejected.empty:
        return
    records = []
    for _, r in rejected.iterrows():
        raw = r.drop(labels=["reason_code"], errors="ignore").to_json(date_format="iso")
        records.append((run_id, batch, None if pd.isna(r.get("order_id")) else str(r.get("order_id")), str(r.reason_code), raw, now()))
    conn.executemany("INSERT INTO quarantine_records(run_id, source_batch, order_id, reason_code, raw_record, quarantined_at) VALUES(?,?,?,?,?,?)", records)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rejected.columns))
        if not exists:
            writer.writeheader()
        for _, r in rejected.iterrows():
            writer.writerow({k: "" if pd.isna(v) else str(v) for k, v in r.items()})


def load(conn: sqlite3.Connection, clean: pd.DataFrame, batch: int) -> int:
    """Load dates and facts atomically. Updated records win only if newer."""
    if clean.empty:
        return 0
    dates = clean["order_datetime"].dt.date.drop_duplicates()
    conn.executemany("INSERT OR IGNORE INTO dim_date(date_key, full_date, day, month, quarter, year) VALUES(?,?,?,?,?,?)",
                     [(int(d.strftime("%Y%m%d")), d.isoformat(), d.day, d.month, (d.month - 1) // 3 + 1, d.year) for d in dates])
    customers = dict(conn.execute("SELECT customer_id, customer_key FROM dim_customer"))
    products = dict(conn.execute("SELECT product_id, product_key FROM dim_product"))
    rows = []
    for r in clean.itertuples(index=False):
        rows.append((str(r.order_id), int(r.order_datetime.strftime("%Y%m%d")), customers[str(r.customer_id)], products[str(r.product_id)],
                     float(r.quantity), float(r.unit_price), float(r.discount_pct), float(r.gross_amount), float(r.net_amount),
                     str(r.payment_method), str(r.sales_channel), r.updated_at.isoformat(), batch))
    before = conn.total_changes
    conn.executemany("""INSERT INTO fact_sales(order_id,date_key,customer_key,product_key,quantity,unit_price,discount_pct,gross_amount,net_amount,payment_method,sales_channel,updated_at,source_batch)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(order_id) DO UPDATE SET date_key=excluded.date_key, customer_key=excluded.customer_key, product_key=excluded.product_key,
        quantity=excluded.quantity, unit_price=excluded.unit_price, discount_pct=excluded.discount_pct, gross_amount=excluded.gross_amount,
        net_amount=excluded.net_amount, payment_method=excluded.payment_method, sales_channel=excluded.sales_channel,
        updated_at=excluded.updated_at, source_batch=excluded.source_batch WHERE excluded.updated_at > fact_sales.updated_at""", rows)
    return conn.total_changes - before


def export_run_log(conn: sqlite3.Connection, path: Path) -> None:
    pd.read_sql_query("SELECT * FROM pipeline_run_log ORDER BY started_at", conn).to_csv(path, index=False)


def run_batch(config: PipelineConfig, batch: int) -> dict[str, object]:
    run_id, started = f"batch_{batch}_{datetime.now().strftime('%Y%m%dT%H%M%S%f')}", now()
    conn = connect(config.output_db)
    create_schema(conn)
    watermark_before = conn.execute("SELECT MAX(updated_at) FROM fact_sales").fetchone()[0]
    try:
        with conn:
            seed_dimensions(conn, config)
            raw = extract(config, batch)
            cids = set(pd.read_sql_query("SELECT customer_id FROM dim_customer", conn).customer_id)
            pids = set(pd.read_sql_query("SELECT product_id FROM dim_product", conn).product_id)
            clean, rejected, duplicates = validate_transform(raw, config, cids, pids)
            append_quarantine(conn, config.quarantine_path, rejected, run_id, batch)
            loaded = load(conn, clean, batch)
            watermark_after = conn.execute("SELECT MAX(updated_at) FROM fact_sales").fetchone()[0]
            row = (run_id, f"batch_{batch}", started, now(), len(raw), len(clean), len(rejected), duplicates, loaded, watermark_before, watermark_after, "SUCCESS", None)
            conn.execute("INSERT INTO pipeline_run_log VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", row)
        export_run_log(conn, config.run_log_path)
        return dict(zip(["run_id","batch","started_at","ended_at","rows_read","rows_valid","rows_rejected","rows_duplicate","rows_loaded","watermark_before","watermark_after","status","error_message"], row))
    except Exception as exc:
        conn.rollback()
        conn.execute("INSERT OR REPLACE INTO pipeline_run_log VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (run_id, f"batch_{batch}", started, now(), 0, 0, 0, 0, 0, watermark_before, None, "FAILED", str(exc)))
        conn.commit(); export_run_log(conn, config.run_log_path)
        if config.error_mode == "raise":
            raise
        logging.exception("Batch %s failed", batch)
        return {"run_id": run_id, "batch": f"batch_{batch}", "status": "FAILED", "error_message": str(exc)}
    finally:
        conn.close()


def run_pipeline(config: PipelineConfig, batches: Iterable[int] | None = None) -> list[dict[str, object]]:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return [run_batch(config, b) for b in (tuple(batches) if batches is not None else config.batches)]


def acceptance_tests(config: PipelineConfig) -> None:
    conn = connect(config.output_db)
    try:
        assert conn.execute("SELECT COUNT(*) = COUNT(DISTINCT order_id) FROM fact_sales").fetchone()[0]
        assert conn.execute("""SELECT COUNT(*) FROM fact_sales f LEFT JOIN dim_customer c ON f.customer_key=c.customer_key
            LEFT JOIN dim_product p ON f.product_key=p.product_key LEFT JOIN dim_date d ON f.date_key=d.date_key
            WHERE c.customer_key IS NULL OR p.product_key IS NULL OR d.date_key IS NULL""").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM fact_sales WHERE quantity <= 0 OR unit_price <= 0 OR net_amount < 0").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM quarantine_records WHERE reason_code IS NULL OR reason_code='' ").fetchone()[0] == 0
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=r"C:\Users\nonthapat\Downloads\Python_Data_Pipeline_Lab_Dataset (1).xlsx")
    parser.add_argument("--batch", type=int, action="append", choices=(1, 2, 3))
    parser.add_argument("--acceptance-sequence", action="store_true", help="run 1, 1 again, 2, 3")
    args = parser.parse_args()
    cfg = PipelineConfig(input_path=Path(args.input))
    batches = (1, 1, 2, 3) if args.acceptance_sequence else (args.batch or list(cfg.batches))
    results = run_pipeline(cfg, batches)
    acceptance_tests(cfg)
    print(pd.DataFrame(results).to_string(index=False))
