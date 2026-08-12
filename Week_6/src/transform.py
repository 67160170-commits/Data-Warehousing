import pandas as pd

PROVINCE_MAP = {
    "bkk": "Bangkok", "bangkok": "Bangkok", "กรุงเทพฯ": "Bangkok",
    "chon buri": "Chonburi", "chonburi": "Chonburi", "ชลบุรี": "Chonburi",
    "chanthaburi": "Chanthaburi", "จันทบุรี": "Chanthaburi",
    "rayong": "Rayong", "ระยอง": "Rayong",
}

def transform(raw):
    customers = raw["customers"].copy()
    products = raw["products"].copy()
    orders = raw["orders"].copy()

    # Customers
    customers = customers.drop_duplicates(subset=["customer_id"], keep="first").copy()
    customers["province"] = (
        customers["province"].astype("string").str.strip().str.lower()
        .map(PROVINCE_MAP)
        .fillna("Unknown")
    )

    # Products: flatten nested JSON fields already normalized by extract
    products = products.rename(columns={
        "category.name": "category",
        "pricing.price": "price",
    })
    products["price"] = pd.to_numeric(
        products["price"].astype("string").str.replace(",", "", regex=False),
        errors="coerce"
    )
    products["category"] = products["category"].fillna("Unknown")
    products = products[["product_id", "product_name", "category", "price"]].copy()

    # Orders
    orders = orders.drop_duplicates(subset=["order_id"], keep="first").copy()
    orders["status"] = orders["status"].astype("string").str.strip().str.lower()
    orders["parsed_date"] = pd.to_datetime(
        orders["order_date"], errors="coerce", format="mixed", dayfirst=True
    )

    invalid_mask = (
        (orders["qty"] <= 0)
        | (orders["unit_price"] <= 0)
        | (orders["discount_pct"] < 0)
        | (orders["discount_pct"] > 100)
        | (orders["parsed_date"].isna())
    )

    rejects = orders.loc[invalid_mask].copy()
    rejects["reject_reason"] = invalid_mask[invalid_mask].index.map(
        lambda _: ""
    )
    # Build explicit reasons for auditability
    reasons = []
    for _, r in rejects.iterrows():
        rr = []
        if r["qty"] <= 0: rr.append("qty <= 0")
        if r["unit_price"] <= 0: rr.append("unit_price <= 0")
        if r["discount_pct"] < 0 or r["discount_pct"] > 100:
            rr.append("discount_pct outside 0-100")
        if pd.isna(r["parsed_date"]): rr.append("invalid date")
        reasons.append("; ".join(rr))
    rejects["reject_reason"] = reasons

    valid_orders = orders.loc[~invalid_mask].copy()
    valid_orders = valid_orders[
        valid_orders["status"].isin(["paid", "completed"])
    ].copy()

    valid_orders["order_date"] = valid_orders["parsed_date"].dt.strftime("%Y-%m-%d")

    # Master-data joins; missing customer/product goes to rejects.
    merged = valid_orders.merge(
        customers, on="customer_id", how="left", indicator="_customer_match"
    ).merge(
        products, on="product_id", how="left", indicator="_product_match"
    )

    missing_master = merged[
        (merged["_customer_match"] != "both")
        | (merged["_product_match"] != "both")
    ].copy()

    if not missing_master.empty:
        extra_reasons = []
        for _, r in missing_master.iterrows():
            rr = []
            if r["_customer_match"] != "both": rr.append("customer not found")
            if r["_product_match"] != "both": rr.append("product not found")
            extra_reasons.append("; ".join(rr))
        missing_master["reject_reason"] = extra_reasons
        rejects = pd.concat([rejects, missing_master], ignore_index=True)

    fact = merged[
        (merged["_customer_match"] == "both")
        & (merged["_product_match"] == "both")
    ].copy()

    fact["gross_amount"] = fact["qty"] * fact["unit_price"]
    fact["discount_amount"] = fact["gross_amount"] * fact["discount_pct"] / 100
    fact["sales_amount"] = fact["gross_amount"] - fact["discount_amount"]

    fact = fact[[
        "order_id", "customer_id", "product_id", "order_date",
        "qty", "unit_price", "discount_pct", "sales_amount"
    ]]

    rejects.to_csv(
        __import__("pathlib").Path(__file__).resolve().parents[1] / "output" / "rejects.csv",
        index=False,
        encoding="utf-8-sig"
    )

    return {
        "customers": customers,
        "products": products,
        "orders": valid_orders,
        "fact_sales": fact,
        "rejects": rejects,
        "stores": raw["stores"].copy(),
    }
