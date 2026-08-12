import json
import sqlite3
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]

def extract():
    customers = pd.read_csv(BASE_DIR / "data" / "customers.csv")
    orders = pd.read_csv(BASE_DIR / "data" / "orders.csv")

    with open(BASE_DIR / "data" / "products.json", encoding="utf-8") as f:
        products = pd.json_normalize(json.load(f))

    con = sqlite3.connect(BASE_DIR / "data" / "store.db")
    try:
        stores = pd.read_sql_query("SELECT * FROM stores", con)
    finally:
        con.close()

    return {
        "customers": customers,
        "orders": orders,
        "products": products,
        "stores": stores,
    }
