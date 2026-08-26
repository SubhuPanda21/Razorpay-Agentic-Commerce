from src.db.models import Merchant, Order, PaymentAttempt
from src.agents import finance_agent


def test_reconcile_matches_successful_order(db_session):
    merchant = db_session.query(Merchant).first()
    order = Order(merchant_id=merchant.id, buyer_agent_id="buyer-y", product_id=1, quantity=1, total_amount=500, status="paid")
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    db_session.add(PaymentAttempt(order_id=order.id, method="upi", amount=500, status="success", gateway_ref="ref1"))
    db_session.commit()
    db_session.refresh(order)

    rec = finance_agent.reconcile(db_session, order)
    assert rec.matched is True
    assert rec.exception_reason is None


def test_reconcile_flags_no_successful_attempt(db_session):
    merchant = db_session.query(Merchant).first()
    order = Order(merchant_id=merchant.id, buyer_agent_id="buyer-z", product_id=1, quantity=1, total_amount=500, status="failed")
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    rec = finance_agent.reconcile(db_session, order)
    assert rec.matched is False
    assert rec.exception_reason == "no_successful_payment_attempt"
