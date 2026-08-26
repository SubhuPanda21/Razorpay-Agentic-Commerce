"""Shopping agent (Track 01).

Owns one job: turn a buyer's natural-language request into a selected,
in-stock product, with a stated reason - via explicit tools, not direct
database access. The orchestrator coordinates; this agent decides.
"""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.db.models import Product
from src.tools import catalog_tools


@dataclass
class SelectionResult:
    product: Product | None
    reasoning: str
    in_stock: bool = True


def select_product(db: Session, query: str, merchant_id: int, quantity: int) -> SelectionResult:
    matches = catalog_tools.search_catalog(db, query, merchant_id)
    if not matches:
        return SelectionResult(product=None, reasoning=f"No product matched query '{query}'.")

    product = matches[0]
    reasoning = f"Best keyword match for '{query}' among {len(matches)} candidate(s): '{product.name}'."

    if not catalog_tools.check_inventory(product, quantity):
        return SelectionResult(
            product=product,
            reasoning=reasoning,
            in_stock=False,
        )
    return SelectionResult(product=product, reasoning=reasoning, in_stock=True)
