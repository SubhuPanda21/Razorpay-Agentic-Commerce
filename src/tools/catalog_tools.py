"""Catalog and inventory tools exposed to the shopping agent.

These are the explicit, named capabilities the agent calls - not the
agent reaching directly into catalog_service/db. Each has an
MCP-style schema so it's demonstrably tool-calling, not just a
function call dressed up as one.
"""
from sqlalchemy.orm import Session

from src.db.models import Product
from src.catalog.catalog_service import search_catalog as _search_catalog


def search_catalog(db: Session, query: str, merchant_id: int, top_k: int = 3) -> list[Product]:
    return _search_catalog(db, query, merchant_id, top_k)


def check_inventory(product: Product, quantity: int) -> bool:
    return product.stock >= quantity


TOOL_SCHEMAS = [
    {
        "name": "search_catalog",
        "description": "Search a merchant's product catalog by natural-language query.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "merchant_id": {"type": "integer"},
                "top_k": {"type": "integer", "default": 3},
            },
            "required": ["query", "merchant_id"],
        },
    },
    {
        "name": "check_inventory",
        "description": "Check whether a product has enough stock for the requested quantity.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "integer"},
                "quantity": {"type": "integer"},
            },
            "required": ["product_id", "quantity"],
        },
    },
]
