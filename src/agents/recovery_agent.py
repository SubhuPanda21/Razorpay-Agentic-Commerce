"""Recovery agent (Track 3: AI Revenue Recovery).

Given a failed payment attempt, decides the next intervention and
executes it via the gateway - bounded by config.recovery_max_attempts
and an explicit stopping rule so it can never retry forever or escalate
charges silently.
"""
from sqlalchemy.orm import Session

from src.config import settings
from src.db.models import Order, RecoveryAttempt
from src.gateway.razorpay_client import PaymentGateway
from src.tools import payment_tools
from src.audit.audit_log import record

# reason -> next method to try (simple, explainable routing table)
_STRATEGY_TABLE = {
    "insufficient_funds": "card",
    "card_declined": "upi",
    "network_error": None,  # retry same method
    "bank_timeout": None,   # retry same method
}


def _next_strategy(failure_reason: str, current_method: str) -> tuple[str, str]:
    alt = _STRATEGY_TABLE.get(failure_reason)
    if alt and alt != current_method:
        return alt, f"retry_alt_method:{alt}"
    return current_method, f"retry_same_method:{current_method}"


def recover(db: Session, order: Order, gateway: PaymentGateway, first_failure_reason: str) -> Order:
    """Runs the bounded recovery loop. Mutates and returns the order."""
    method = order.payment_attempts[-1].method if order.payment_attempts else "upi"
    failure_reason = first_failure_reason
    attempt_number = 1

    while attempt_number <= settings.recovery_max_attempts:
        method, strategy = _next_strategy(failure_reason, method)

        result = payment_tools.initiate_payment(db, gateway, order, method, attempt_seed=attempt_number)

        recovery_row = RecoveryAttempt(
            order_id=order.id,
            attempt_number=attempt_number,
            strategy=strategy,
            status="success" if result.success else "failed",
        )
        db.add(recovery_row)
        db.commit()

        record(
            db,
            actor="recovery_agent",
            action="recovery_attempt",
            detail={"attempt": attempt_number, "strategy": strategy, "result": recovery_row.status},
            order_id=order.id,
        )

        if result.success:
            order.status = "recovered"
            db.commit()
            record(db, "recovery_agent", "recovery_succeeded", {"attempt": attempt_number}, order.id)
            return order

        failure_reason = result.failure_reason
        attempt_number += 1

    # Stopping rule hit: mark failed, escalate rather than retry forever.
    order.status = "failed"
    db.commit()
    record(
        db,
        actor="recovery_agent",
        action="recovery_stopped",
        detail={"reason": "max_attempts_reached", "max_attempts": settings.recovery_max_attempts},
        order_id=order.id,
    )
    return order
