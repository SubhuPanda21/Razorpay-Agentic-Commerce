from src.db.models import Merchant, Order
from src.policies import policy_engine


def _make_order(db_session, amount):
    merchant = db_session.query(Merchant).first()
    order = Order(merchant_id=merchant.id, buyer_agent_id="buyer-p", product_id=1, quantity=1, total_amount=amount)
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


def test_order_within_budget_is_approved(db_session):
    order = _make_order(db_session, 5000)
    decision = policy_engine.evaluate(order, budget_limit=20000, authorized=False)
    assert decision.approved is True


def test_order_over_budget_is_rejected_even_if_authorized(db_session):
    order = _make_order(db_session, 25000)
    decision = policy_engine.evaluate(order, budget_limit=20000, authorized=True)
    assert decision.approved is False
    assert "spending limit" in decision.reason


def test_high_value_order_requires_authorization(db_session):
    order = _make_order(db_session, 15000)
    unauthorized = policy_engine.evaluate(order, budget_limit=None, authorized=False)
    authorized = policy_engine.evaluate(order, budget_limit=None, authorized=True)

    assert unauthorized.approved is False
    assert "authorization" in unauthorized.reason
    assert authorized.approved is True
