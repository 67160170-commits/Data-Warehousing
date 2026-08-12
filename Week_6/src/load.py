import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "data" / "warehouse" / "warehouse.db"

def load(data):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS dim_customer (
        customer_id TEXT PRIMARY KEY,
        name TEXT,
        province TEXT,
        email TEXT
    );

    CREATE TABLE IF NOT EXISTS dim_product (
        product_id TEXT PRIMARY KEY,
        product_name TEXT,
        category TEXT,
        price REAL
    );

    CREATE TABLE IF NOT EXISTS fact_sales (
        order_id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL,
        product_id TEXT NOT NULL,
        order_date TEXT NOT NULL,
        qty INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        discount_pct REAL NOT NULL,
        sales_amount REAL NOT NULL,
        FOREIGN KEY (customer_id) REFERENCES dim_customer(customer_id),
        FOREIGN KEY (product_id) REFERENCES dim_product(product_id)
    );
    """)

    # Idempotent load: rerunning the pipeline replaces the same business keys.
    cur.executemany(
        """INSERT OR REPLACE INTO dim_customer
        (customer_id, name, province, email) VALUES (?, ?, ?, ?)""",
        data["customers"][["customer_id","name","province","email"]].itertuples(index=False, name=None)
    )
    cur.executemany(
        """INSERT OR REPLACE INTO dim_product
        (product_id, product_name, category, price) VALUES (?, ?, ?, ?)""",
        data["products"][["product_id","product_name","category","price"]].itertuples(index=False, name=None)
    )
    cur.executemany(
        """INSERT OR REPLACE INTO fact_sales
        (order_id, customer_id, product_id, order_date, qty, unit_price, discount_pct, sales_amount)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        data["fact_sales"].itertuples(index=False, name=None)
    )

    con.commit()
    con.close()
    return DB_PATH
