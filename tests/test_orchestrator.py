from src.agents.orchestrator import run_checkout
from src.db.models import Merchant


def test_full_checkout_flow_reaches_terminal_status(db_session):
    merchant = db_session.query(Merchant).first()
    result = run_checkout(db_session, merchant.id, "buyer-e2e", "test widget")

    assert result.order_id is not None
    assert result.status in ("paid", "recovered", "failed", "blocked")
    assert len(result.audit_trail) > 0
    # every run must at least log product selection and order creation
    actions = [step["action"] for step in result.audit_trail]
    assert "product_selected" in actions
    assert "order_created" in actions


def test_out_of_stock_short_circuits(db_session):
    merchant = db_session.query(Merchant).first()
    result = run_checkout(db_session, merchant.id, "buyer-oos", "test widget", quantity=999)
    assert result.status == "failed"
    assert "out of stock" in result.message
