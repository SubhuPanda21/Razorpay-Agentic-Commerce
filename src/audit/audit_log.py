"""Append-only audit trail. Called by every agent at every decision point."""
import json
from sqlalchemy.orm import Session

from src.db.models import AuditLog


def record(db: Session, actor: str, action: str, detail: dict, order_id: int | None = None) -> AuditLog:
    entry = AuditLog(
        order_id=order_id,
        actor=actor,
        action=action,
        detail=json.dumps(detail, default=str),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_trail(db: Session, order_id: int) -> list[dict]:
    rows = (
        db.query(AuditLog)
        .filter(AuditLog.order_id == order_id)
        .order_by(AuditLog.created_at.asc())
        .all()
    )
    return [
        {
            "actor": r.actor,
            "action": r.action,
            "detail": json.loads(r.detail),
            "at": r.created_at.isoformat(),
        }
        for r in rows
    ]
