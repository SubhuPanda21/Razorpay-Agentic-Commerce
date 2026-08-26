"""Finance agent (Track 4: AI Finance Controller).

Closes the loop after checkout/recovery: matches the order's expected
amount against what actually settled, and reports an honest exception
when it can't reconcile - no cherry-picked matches.
"""
from sqlalchemy.orm import Session

from src.db.models import Order, ReconciliationRecord
from src.audit.audit_log import record


def reconcile(db: Session, order: Order) -> ReconciliationRecord:
    successful_attempt = next(
        (a for a in order.payment_attempts if a.status == "success"), None
    )
    settled_amount = successful_attempt.amount if successful_attempt else None

    matched = successful_attempt is not None and settled_amount == order.total_amount
    exception_reason = None
    if successful_attempt is None:
        exception_reason = "no_successful_payment_attempt"
    elif settled_amount != order.total_amount:
        exception_reason = f"amount_mismatch: expected {order.total_amount}, settled {settled_amount}"

    rec = ReconciliationRecord(
        order_id=order.id,
        matched=matched,
        expected_amount=order.total_amount,
        settled_amount=settled_amount,
        exception_reason=exception_reason,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    record(
        db,
        actor="finance_agent",
        action="reconciled",
        detail={"matched": matched, "exception_reason": exception_reason},
        order_id=order.id,
    )
    return rec


def summary(db: Session) -> dict:
    """Match-rate + exception list across all reconciled orders - not just one cherry-picked case."""
    records = db.query(ReconciliationRecord).all()
    total = len(records)
    matched = sum(1 for r in records if r.matched)
    exceptions = [
        {"order_id": r.order_id, "reason": r.exception_reason}
        for r in records
        if not r.matched
    ]
    match_rate = round(matched / total, 3) if total else 0.0
    return {"total_records": total, "matched": matched, "match_rate": match_rate, "exceptions": exceptions}
