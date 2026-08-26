"""Payment tools: initiating a charge and recording the attempt.

Both the orchestrator's first attempt and recovery_agent's retries go
through `initiate_payment`, so there is exactly one place that writes
a PaymentAttempt row - no duplicated bookkeeping logic to drift apart.
"""
from sqlalchemy.orm import Session

from src.db.models import Order, PaymentAttempt
from src.gateway.razorpay_client import PaymentGateway, PaymentResult


def initiate_payment(
    db: Session, gateway: PaymentGateway, order: Order, method: str, attempt_seed: int = 0
) -> PaymentResult:
    result = gateway.charge(order.id, order.total_amount, method, attempt_seed=attempt_seed)
    db.add(
        PaymentAttempt(
            order_id=order.id,
            method=method,
            amount=order.total_amount,
            status="success" if result.success else "failed",
            failure_reason=result.failure_reason,
            gateway_ref=result.gateway_ref,
        )
    )
    db.commit()
    return result


TOOL_SCHEMAS = [
    {
        "name": "initiate_payment",
        "description": "Attempt to charge an order via the configured payment method.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "integer"},
                "method": {"type": "string", "enum": ["upi", "card", "netbanking"]},
            },
            "required": ["order_id", "method"],
        },
    },
]
