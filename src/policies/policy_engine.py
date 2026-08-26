"""Policy engine: deterministic, non-overridable business rules.

This is deliberately separate from risk_agent. risk_agent scores
*probabilistic* fraud-shaped signals (velocity, amount anomaly) and can
land on "hold" for human review. The policy engine enforces *hard*
rules that no agent, LLM, or retry loop can talk its way around:

    LLM/agent -> tool call -> POLICY ENGINE -> gateway

A policy rejection is final for that order - the checkout flow does
not retry around it, only around gateway-level payment failures.
"""
from dataclasses import dataclass

from src.config import settings
from src.db.models import Order


@dataclass
class PolicyDecision:
    approved: bool
    reason: str | None = None


def check_spending_limit(order: Order, budget_limit: float | None) -> PolicyDecision:
    """Hard cap on order value. `budget_limit` is caller-supplied (e.g. a
    buyer agent's configured budget); falls back to a system-wide default cap.
    """
    cap = budget_limit if budget_limit is not None else settings.default_order_cap
    if order.total_amount > cap:
        return PolicyDecision(
            approved=False,
            reason=f"order amount {order.total_amount} exceeds spending limit {cap}",
        )
    return PolicyDecision(approved=True)


def check_authorization(order: Order, authorized: bool) -> PolicyDecision:
    """Orders above a threshold require explicit authorization (simulating a
    human-in-the-loop approval) - the agent cannot self-approve high-value spend.
    """
    if order.total_amount > settings.authorization_required_above and not authorized:
        return PolicyDecision(
            approved=False,
            reason=(
                f"order amount {order.total_amount} exceeds "
                f"{settings.authorization_required_above}; explicit authorization required"
            ),
        )
    return PolicyDecision(approved=True)


def evaluate(order: Order, budget_limit: float | None, authorized: bool) -> PolicyDecision:
    """Runs every hard rule; the first failure wins (fail-closed)."""
    for check in (
        lambda: check_spending_limit(order, budget_limit),
        lambda: check_authorization(order, authorized),
    ):
        decision = check()
        if not decision.approved:
            return decision
    return PolicyDecision(approved=True)
