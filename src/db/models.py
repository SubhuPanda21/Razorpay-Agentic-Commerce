"""SQLAlchemy ORM models for the whole system.

One coherent schema shared by the checkout flow (Track 1) and the
three modules it gates through: risk (Track 2), recovery (Track 3),
and finance/reconciliation (Track 4).
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)  # organization / display label

    # Real account fields - nullable so the seeded demo merchant (id=1,
    # used by the public homepage/dashboard) needs none of these.
    email = Column(String(160), unique=True, nullable=True)
    password_hash = Column(String(160), nullable=True)
    api_key = Column(String(64), unique=True, nullable=True)
    display_name = Column(String(80), nullable=True)
    role = Column(String(80), nullable=True)
    building_description = Column(String(400), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    products = relationship("Product", back_populates="merchant")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id"), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    category = Column(String(80), default="general")
    price = Column(Float, nullable=False)  # in INR
    stock = Column(Integer, default=0)

    merchant = relationship("Merchant", back_populates="products")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id"), nullable=False)
    buyer_agent_id = Column(String(120), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, default=1)
    total_amount = Column(Float, nullable=False)
    status = Column(String(30), default="created")
    razorpay_order_id = Column(String(80), nullable=True)  # links webhooks back to this order
    # created -> risk_checked -> paid / recovered / failed / blocked
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    product = relationship("Product")
    payment_attempts = relationship("PaymentAttempt", back_populates="order")
    risk_assessment = relationship("RiskAssessment", back_populates="order", uselist=False)
    recovery_attempts = relationship("RecoveryAttempt", back_populates="order")
    reconciliation = relationship("ReconciliationRecord", back_populates="order", uselist=False)


class PaymentAttempt(Base):
    __tablename__ = "payment_attempts"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    method = Column(String(30), nullable=False)  # upi, card, netbanking
    amount = Column(Float, nullable=False, default=0.0)
    status = Column(String(30), nullable=False)  # success, failed
    failure_reason = Column(String(120), nullable=True)
    gateway_ref = Column(String(80), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    order = relationship("Order", back_populates="payment_attempts")


class RiskAssessment(Base):
    """Track 2 output: strictly defense-only gate before payment."""
    __tablename__ = "risk_assessments"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, unique=True)
    score = Column(Float, nullable=False)  # 0..1
    decision = Column(String(20), nullable=False)  # allow, hold, block
    reasons = Column(Text, default="[]")  # JSON list of strings
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    order = relationship("Order", back_populates="risk_assessment")


class RecoveryAttempt(Base):
    """Track 3 output: bounded, ruled recovery workflow."""
    __tablename__ = "recovery_attempts"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    attempt_number = Column(Integer, nullable=False)
    strategy = Column(String(60), nullable=False)  # e.g. "retry_alt_method:card"
    status = Column(String(30), nullable=False)  # success, failed, stopped
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    order = relationship("Order", back_populates="recovery_attempts")


class ReconciliationRecord(Base):
    """Track 4 output: matched/exception ledger entry per order."""
    __tablename__ = "reconciliation_records"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, unique=True)
    matched = Column(Boolean, default=False)
    expected_amount = Column(Float, nullable=False)
    settled_amount = Column(Float, nullable=True)
    exception_reason = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    order = relationship("Order", back_populates="reconciliation")


class AuditLog(Base):
    """Append-only trail. Every agent decision writes here.

    This is what makes the whole run explainable end to end -
    the literal requirement in Track 1's bar.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    actor = Column(String(40), nullable=False)  # checkout_agent, risk_agent, ...
    action = Column(String(80), nullable=False)
    detail = Column(Text, default="{}")  # JSON blob
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
