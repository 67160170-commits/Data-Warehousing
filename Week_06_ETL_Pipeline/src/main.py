import logging
from pathlib import Path
from .extract import extract
from .transform import transform
from .load import load
from .validate import validate

BASE_DIR = Path(__file__).resolve().parents[1]
(BASE_DIR / "logs").mkdir(exist_ok=True)

logging.basicConfig(
    filename=BASE_DIR / "logs" / "etl.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

def main():
    logging.info("ETL started")
    raw = extract()
    logging.info(
        "Extracted customers=%s orders=%s products=%s stores=%s",
        len(raw["customers"]), len(raw["orders"]),
        len(raw["products"]), len(raw["stores"])
    )

    transformed = transform(raw)
    logging.info(
        "Transformed valid fact rows=%s rejects=%s",
        len(transformed["fact_sales"]), len(transformed["rejects"])
    )

    load(transformed)
    result = validate(transformed)
    logging.info("Validation result=%s", result)

    print("ETL completed")
    print(result)

if __name__ == "__main__":
    main()
