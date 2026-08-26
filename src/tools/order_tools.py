"""Order tools: the agent's only way to create/read orders."""
from sqlalchemy.orm import Session

from src.db.models import Order, Product


def create_order(
    db: Session, merchant_id: int, buyer_agent_id: str, product: Product, quantity: int
) -> Order:
    order = Order(
        merchant_id=merchant_id,
        buyer_agent_id=buyer_agent_id,
        product_id=product.id,
        quantity=quantity,
        total_amount=round(product.price * quantity, 2),
        status="created",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def deduct_stock(db: Session, product: Product, quantity: int) -> None:
    product.stock -= quantity
    db.commit()


TOOL_SCHEMAS = [
    {
        "name": "create_order",
        "description": "Create a pending order for a product + quantity at the merchant's current price.",
        "input_schema": {
            "type": "object",
            "properties": {
                "merchant_id": {"type": "integer"},
                "buyer_agent_id": {"type": "string"},
                "product_id": {"type": "integer"},
                "quantity": {"type": "integer", "default": 1},
            },
            "required": ["merchant_id", "buyer_agent_id", "product_id"],
        },
    },
]
