"""FastAPI application - the deployable surface of the whole system."""
import os

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db.database import get_session, init_db
from src.db.models import Product, Order
from src.agents.orchestrator import run_checkout
from src.agents.finance_agent import summary as finance_summary
from src.audit.audit_log import get_trail
from scripts.seed_data import seed as seed_catalog

FRONTEND_INDEX = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "index.html")

app = FastAPI(
    title="Razorpay Agentic Commerce",
    description="An AI buyer-agent checkout flow gated by risk, backed by recovery, closed by reconciliation.",
    version="1.0.0",
)


@app.on_event("startup")
def _startup():
    init_db()
    seed_catalog()  # idempotent — no-ops if already seeded, so redeploys are safe


@app.get("/")
def root():
    return FileResponse(FRONTEND_INDEX)


class PurchaseRequest(BaseModel):
    merchant_id: int
    buyer_agent_id: str
    query: str
    quantity: int = 1
    preferred_method: str = "upi"
    budget_limit: float | None = None  # buyer-agent's configured spending cap, if any
    authorized: bool = False           # explicit human authorization for high-value orders


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/catalog/{merchant_id}")
def get_catalog(merchant_id: int, db: Session = Depends(get_session)):
    products = db.query(Product).filter(Product.merchant_id == merchant_id).all()
    return [
        {"id": p.id, "name": p.name, "price": p.price, "stock": p.stock, "category": p.category}
        for p in products
    ]


@app.post("/purchase")
def purchase(req: PurchaseRequest, db: Session = Depends(get_session)):
    result = run_checkout(
        db,
        merchant_id=req.merchant_id,
        buyer_agent_id=req.buyer_agent_id,
        query=req.query,
        quantity=req.quantity,
        preferred_method=req.preferred_method,
        budget_limit=req.budget_limit,
        authorized=req.authorized,
    )
    return {
        "order_id": result.order_id,
        "status": result.status,
        "message": result.message,
        "audit_trail": result.audit_trail,
    }


@app.get("/orders/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_session)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    return {
        "id": order.id,
        "status": order.status,
        "total_amount": order.total_amount,
        "buyer_agent_id": order.buyer_agent_id,
        "product": order.product.name if order.product else None,
    }


@app.get("/orders/{order_id}/audit")
def order_audit(order_id: int, db: Session = Depends(get_session)):
    trail = get_trail(db, order_id)
    if not trail:
        raise HTTPException(404, "No audit trail for this order")
    return trail


@app.get("/finance/summary")
def get_finance_summary(db: Session = Depends(get_session)):
    return finance_summary(db)
