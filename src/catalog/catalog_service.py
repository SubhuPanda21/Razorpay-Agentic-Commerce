"""Agent-readable catalog search.

This is the "agent-readable catalog" example direction from Track 1:
a merchant's products exposed as a tool an AI buyer agent can query in
natural language, not just a human-facing product grid.
"""
from sqlalchemy.orm import Session

from src.db.models import Product


def search_catalog(db: Session, query: str, merchant_id: int, top_k: int = 3) -> list[Product]:
    """Naive but effective keyword-overlap search over name/description/category.

    Swappable later for embedding-based search without touching callers -
    the interface (query string -> ranked products) stays the same.
    """
    query_terms = {t.lower() for t in query.split() if len(t) > 2}
    products = db.query(Product).filter(Product.merchant_id == merchant_id).all()

    def score(p: Product) -> int:
        haystack = f"{p.name} {p.description} {p.category}".lower()
        return sum(1 for t in query_terms if t in haystack)

    ranked = sorted(products, key=score, reverse=True)
    ranked = [p for p in ranked if score(p) > 0] or products  # fall back to full catalog
    return ranked[:top_k]


def as_tool_schema() -> dict:
    """MCP-style tool schema describing this capability to an agent/LLM."""
    return {
        "name": "search_catalog",
        "description": "Search a merchant's product catalog by natural-language query.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What the buyer is looking for"},
                "merchant_id": {"type": "integer"},
            },
            "required": ["query", "merchant_id"],
        },
    }
