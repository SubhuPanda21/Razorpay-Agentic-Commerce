"""UAP-inspired trust registry (simulated - NPCI's real UAP has no public
implementation yet, per the track's own brief). An agent must be
registered against a merchant, with a declared spending ceiling, before
it's trusted to transact at all - independent of and prior to the AP2
mandate and the policy engine's own per-order cap.
"""
from sqlalchemy.orm import Session

from src.db.models import TrustedAgent


def register(db: Session, agent_id: str, merchant_id: int, spending_ceiling: float) -> TrustedAgent:
    existing = (
        db.query(TrustedAgent)
        .filter(TrustedAgent.agent_id == agent_id, TrustedAgent.merchant_id == merchant_id)
        .first()
    )
    if existing:
        existing.spending_ceiling = spending_ceiling
        db.commit()
        return existing

    entry = TrustedAgent(agent_id=agent_id, merchant_id=merchant_id, spending_ceiling=spending_ceiling)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def is_trusted(db: Session, agent_id: str, merchant_id: int, amount: float) -> tuple[bool, str | None]:
    entry = (
        db.query(TrustedAgent)
        .filter(TrustedAgent.agent_id == agent_id, TrustedAgent.merchant_id == merchant_id)
        .first()
    )
    if not entry:
        return False, "agent_not_registered_in_trust_registry"
    if amount > entry.spending_ceiling:
        return False, f"order amount {amount} exceeds registered trust ceiling {entry.spending_ceiling}"
    return True, None
