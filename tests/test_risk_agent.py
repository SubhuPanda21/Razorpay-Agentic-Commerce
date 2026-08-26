from src.db.models import Merchant, Order
from src.agents import risk_agent


def test_low_risk_order_is_allowed(db_session):
    merchant = db_session.query(Merchant).first()
    order = Order(merchant_id=merchant.id, buyer_agent_id="buyer-a", product_id=1, quantity=1, total_amount=500)
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    assessment = risk_agent.assess(db_session, order)
    assert assessment.decision == "allow"
    assert assessment.score < risk_agent.settings.risk_hold_threshold


def test_velocity_triggers_block(db_session):
    merchant = db_session.query(Merchant).first()
    buyer = "buyer-fast"

    # push orders past the velocity limit
    for _ in range(6):
        order = Order(merchant_id=merchant.id, buyer_agent_id=buyer, product_id=1, quantity=1, total_amount=500)
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)
        last_assessment = risk_agent.assess(db_session, order)

    assert last_assessment.decision in ("hold", "block")
