"""Risk agent (Track 2: AI Risk Manager).

Strictly defense-only: this module can only ALLOW, HOLD, or BLOCK an
order before payment. It never initiates a charge, refund, or any
offensive action - deliberately, to stay within the track's own rule
that "anything offense-capable is disqualified."

Two signals, both explainable (no black-box score):
  1. Velocity - too many orders from the same buyer agent in a short window.
  2. Amount anomaly - order far above the merchant's historical average
     (z-score), a classic proxy for card-testing / stolen-instrument abuse.
"""
import json
from datetime import datetime, timedelta, timezone
from statistics import mean, pstdev

from sqlalchemy.orm import Session

from src.config import settings
from src.db.models import Order, RiskAssessment
from src.audit.audit_log import record


def _velocity_score(db: Session, buyer_agent_id: str) -> tuple[float, str | None]:
    window_start = datetime.now(timezone.utc) - timedelta(minutes=settings.velocity_window_minutes)
    recent_count = (
        db.query(Order)
        .filter(Order.buyer_agent_id == buyer_agent_id, Order.created_at >= window_start)
        .count()
    )
    if recent_count >= settings.velocity_max_orders:
        return 1.0, f"{recent_count} orders in last {settings.velocity_window_minutes}min (limit {settings.velocity_max_orders})"
    # linear ramp from 0 to 1 as we approach the limit
    return recent_count / settings.velocity_max_orders, None


def _amount_anomaly_score(db: Session, merchant_id: int, amount: float) -> tuple[float, str | None]:
    history = [
        o.total_amount
        for o in db.query(Order).filter(Order.merchant_id == merchant_id).all()
    ]
    if len(history) < 3:
        return 0.0, None  # not enough history to judge
    mu = mean(history)
    sigma = pstdev(history) or 1.0
    z = (amount - mu) / sigma
    if z <= 1:
        return 0.0, None
    score = min(z / 4, 1.0)  # z=4 -> fully saturated
    return score, f"amount z-score={z:.2f} vs merchant history (mean={mu:.0f})"


def assess(db: Session, order: Order) -> RiskAssessment:
    v_score, v_reason = _velocity_score(db, order.buyer_agent_id)
    a_score, a_reason = _amount_anomaly_score(db, order.merchant_id, order.total_amount)

    # Weighted blend, both signals explainable and independently inspectable
    combined = 0.6 * v_score + 0.4 * a_score
    reasons = [r for r in (v_reason, a_reason) if r]

    if combined >= settings.risk_block_threshold:
        decision = "block"
    elif combined >= settings.risk_hold_threshold:
        decision = "hold"
    else:
        decision = "allow"

    assessment = RiskAssessment(
        order_id=order.id,
        score=round(combined, 3),
        decision=decision,
        reasons=json.dumps(reasons),
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)

    record(
        db,
        actor="risk_agent",
        action="risk_assessed",
        detail={"score": assessment.score, "decision": decision, "reasons": reasons},
        order_id=order.id,
    )
    return assessment
