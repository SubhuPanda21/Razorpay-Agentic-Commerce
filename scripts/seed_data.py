"""Seeds a merchant + catalog from src/catalog/sample_catalog.json.

Run: python -m scripts.seed_data
"""
import json
import os

from src.db.database import SessionLocal, init_db
from src.db.models import Merchant, Product

CATALOG_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "catalog", "sample_catalog.json")


def seed():
    init_db()
    db = SessionLocal()
    try:
        if db.query(Merchant).count() > 0:
            print("Database already seeded. Skipping.")
            return

        with open(CATALOG_PATH) as f:
            data = json.load(f)

        merchant = Merchant(name=data["merchant"])
        db.add(merchant)
        db.commit()
        db.refresh(merchant)

        for p in data["products"]:
            db.add(Product(merchant_id=merchant.id, **p))
        db.commit()

        print(f"Seeded merchant '{merchant.name}' (id={merchant.id}) with {len(data['products'])} products.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
