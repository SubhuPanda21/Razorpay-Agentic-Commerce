"""Checkout orchestrator (Track 1: AI Growth & Agentic Commerce).

Thin coordinator - it holds no business logic itself, only the
sequence in which specialists are consulted:

    shopping_agent (select product)
        -> policy_engine (hard, non-overridable rules)
        -> risk_agent (Track 2 - probabilistic fraud gate)
        -> payment_tools.initiate_payment
        -> [on failure] recovery_agent (Track 3 - bounded retries)
        -> [on success] finance_agent (Track 4 - reconciliation)
        -> audit trail throughout

A policy rejection is final for the order - the flow never retries
around a hard rule, only around gateway-level payment failures.
"""
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from src.agents import shopping_agent, risk_agent, recovery_agent, finance_agent
from src.policies import policy_engine
from src.tools import order_tools, payment_tools
from src.gateway.razorpay_client import get_gateway
from src.audit.audit_log import record, get_trail


@dataclass
class CheckoutResult:
    order_id: int | None
    status: str
    message: str
    audit_trail: list = field(default_factory=list)


@dataclass
class PrepareResult:
    order: object | None
    ready: bool
    status: str
    message: str
    checkout_session: dict | None = None
    audit_trail: list = field(default_factory=list)


def prepare_checkout(
    db: Session,
    merchant_id: int,
    buyer_agent_id: str,
    query: str,
    quantity: int = 1,
    budget_limit: float | None = None,
    authorized: bool = False,
) -> PrepareResult:
    """Steps 1-4 only: select product, create order, policy gate, risk gate.

    Used by the real-payment flow, where the frontend needs a checkout
    session (real Razorpay order + key, or the mock equivalent) BEFORE
    the buyer actually pays - payment itself is finalized separately by
    finalize_payment() once the widget (or simulator) reports back.
    """
    gateway = get_gateway()

    selection = shopping_agent.select_product(db, query, merchant_id, quantity)
    if selection.product is None:
        record(db, "shopping_agent", "no_catalog_match", {"query": query})
        return PrepareResult(None, False, "failed", selection.reasoning)

    product = selection.product
    if not selection.in_stock:
        record(db, "shopping_agent", "out_of_stock", {"product": product.name, "requested": quantity, "stock": product.stock})
        return PrepareResult(None, False, "failed", f"'{product.name}' is out of stock.")

    order = order_tools.create_order(db, merchant_id, buyer_agent_id, product, quantity)
    record(db, "shopping_agent", "product_selected", {"query": query, "product": product.name, "reasoning": selection.reasoning}, order.id)
    record(db, "checkout_agent", "order_created", {"amount": order.total_amount}, order.id)

    policy_decision = policy_engine.evaluate(order, budget_limit, authorized)
    record(db, "policy_engine", "policy_evaluated", {"approved": policy_decision.approved, "reason": policy_decision.reason}, order.id)
    if not policy_decision.approved:
        order.status = "policy_rejected"
        db.commit()
        return PrepareResult(order, False, "policy_rejected", policy_decision.reason, audit_trail=get_trail(db, order.id))

    assessment = risk_agent.assess(db, order)
    if assessment.decision == "block":
        order.status = "blocked"
        db.commit()
        return PrepareResult(order, False, "blocked", "Order blocked by risk gate.", audit_trail=get_trail(db, order.id))

    session = gateway.create_checkout_order(order.id, order.total_amount)
    record(db, "checkout_agent", "checkout_session_created", {"mode": session["mode"], "razorpay_order_id": session["razorpay_order_id"]}, order.id)

    return PrepareResult(order, True, "ready_for_payment", "Ready for payment.", checkout_session=session, audit_trail=get_trail(db, order.id))


def finalize_payment(db: Session, order, preferred_method: str, payload: dict) -> CheckoutResult:
    """Steps 5-7: confirm payment (real signature verification or the
    simulator), recover on failure, reconcile on success."""
    gateway = get_gateway()
    payload = {**payload, "amount": order.total_amount, "method": preferred_method}

    result = gateway.verify_and_capture(order.id, payload)
    db.add(_payment_attempt_row(order, preferred_method, result))
    db.commit()
    record(
        db, "checkout_agent", "payment_attempted",
        {"method": preferred_method, "status": "success" if result.success else "failed", "reason": result.failure_reason},
        order.id,
    )

    if not result.success:
        order = recovery_agent.recover(db, order, gateway, result.failure_reason)
    else:
        order.status = "paid"
        db.commit()

    if order.status in ("paid", "recovered"):
        order_tools.deduct_stock(db, order.product, order.quantity)
        finance_agent.reconcile(db, order)
        msg = f"Order #{order.id} completed via '{order.status}' path for {order.product.name}."
    else:
        msg = f"Order #{order.id} could not be completed ({order.status})."

    return CheckoutResult(order.id, order.status, msg, get_trail(db, order.id))


def _payment_attempt_row(order, method, result):
    from src.db.models import PaymentAttempt
    return PaymentAttempt(
        order_id=order.id, method=method, amount=order.total_amount,
        status="success" if result.success else "failed",
        failure_reason=result.failure_reason, gateway_ref=result.gateway_ref,
    )


def run_checkout(
    db: Session,
    merchant_id: int,
    buyer_agent_id: str,
    query: str,
    quantity: int = 1,
    preferred_method: str = "upi",
    budget_limit: float | None = None,
    authorized: bool = False,
) -> CheckoutResult:
    gateway = get_gateway()

    # 1. Shopping agent selects a product via explicit tools
    selection = shopping_agent.select_product(db, query, merchant_id, quantity)
    if selection.product is None:
        record(db, "shopping_agent", "no_catalog_match", {"query": query})
        return CheckoutResult(None, "failed", selection.reasoning)

    product = selection.product
    if not selection.in_stock:
        record(db, "shopping_agent", "out_of_stock", {"product": product.name, "requested": quantity, "stock": product.stock})
        return CheckoutResult(None, "failed", f"'{product.name}' is out of stock.")

    # 2. Create the order
    order = order_tools.create_order(db, merchant_id, buyer_agent_id, product, quantity)
    record(db, "shopping_agent", "product_selected", {"query": query, "product": product.name, "reasoning": selection.reasoning}, order.id)
    record(db, "checkout_agent", "order_created", {"amount": order.total_amount}, order.id)

    # 3. Policy engine - hard, non-overridable rules (distinct from risk scoring)
    policy_decision = policy_engine.evaluate(order, budget_limit, authorized)
    record(db, "policy_engine", "policy_evaluated", {"approved": policy_decision.approved, "reason": policy_decision.reason}, order.id)
    if not policy_decision.approved:
        order.status = "policy_rejected"
        db.commit()
        return CheckoutResult(order.id, "policy_rejected", policy_decision.reason, get_trail(db, order.id))

    # 4. Risk gate - Track 2, strictly defense-only (allow/hold/block, never offensive)
    assessment = risk_agent.assess(db, order)
    if assessment.decision == "block":
        order.status = "blocked"
        db.commit()
        return CheckoutResult(order.id, "blocked", "Order blocked by risk gate.", get_trail(db, order.id))
    # "hold" proceeds but is flagged in the audit trail for human review;
    # it never silently escalates into an auto-approved higher-risk action.

    # 5. Attempt payment
    result = payment_tools.initiate_payment(db, gateway, order, preferred_method, attempt_seed=0)
    record(
        db, "checkout_agent", "payment_attempted",
        {"method": preferred_method, "status": "success" if result.success else "failed", "reason": result.failure_reason},
        order.id,
    )

    if not result.success:
        # 6. Recovery - Track 3, bounded retries with a stopping rule
        order = recovery_agent.recover(db, order, gateway, result.failure_reason)
    else:
        order.status = "paid"
        db.commit()

    # 7. Reconcile - Track 4, regardless of how payment ultimately resolved
    if order.status in ("paid", "recovered"):
        order_tools.deduct_stock(db, product, quantity)
        finance_agent.reconcile(db, order)
        msg = f"Order #{order.id} completed via '{order.status}' path for {product.name}."
    else:
        msg = f"Order #{order.id} could not be completed ({order.status})."

    return CheckoutResult(order.id, order.status, msg, get_trail(db, order.id))
