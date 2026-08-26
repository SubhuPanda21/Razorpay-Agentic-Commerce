from src.db.models import Merchant, Order
from src.agents import recovery_agent
from src.gateway.razorpay_client import PaymentGateway, PaymentResult


class AlwaysFailGateway(PaymentGateway):
    def charge(self, order_id, amount, method, attempt_seed=0):
        return PaymentResult(success=False, gateway_ref="", failure_reason="network_error")


class SucceedOnThirdGateway(PaymentGateway):
    def charge(self, order_id, amount, method, attempt_seed=0):
        if attempt_seed >= 2:
            return PaymentResult(success=True, gateway_ref="ref123")
        return PaymentResult(success=False, gateway_ref="", failure_reason="bank_timeout")


def _make_order(db_session):
    merchant = db_session.query(Merchant).first()
    order = Order(merchant_id=merchant.id, buyer_agent_id="buyer-x", product_id=1, quantity=1, total_amount=500)
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


def test_recovery_stops_after_max_attempts(db_session):
    order = _make_order(db_session)
    result = recovery_agent.recover(db_session, order, AlwaysFailGateway(), "network_error")
    assert result.status == "failed"
    assert len(order.recovery_attempts) == recovery_agent.settings.recovery_max_attempts


def test_recovery_succeeds_within_bound(db_session):
    order = _make_order(db_session)
    result = recovery_agent.recover(db_session, order, SucceedOnThirdGateway(), "bank_timeout")
    assert result.status == "recovered"
