"""FastAPI application - the deployable surface of the whole system."""
import os

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db.database import get_session, init_db
from src.db.models import Product, Order
from src.agents.orchestrator import run_checkout, prepare_checkout, finalize_payment
from src.agents.finance_agent import summary as finance_summary
from src.audit.audit_log import get_trail
from scripts.seed_data import seed as seed_catalog

FRONTEND_INDEX = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "index.html")
FRONTEND_ABOUT = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "about.html")

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


@app.get("/about")
def about():
    return FileResponse(FRONTEND_ABOUT)


@app.get("/robots.txt")
def robots():
    return Response(
        "User-agent: *\nAllow: /\nSitemap: https://razorpay-agentic-commerce-d5ii.onrender.com/sitemap.xml",
        media_type="text/plain",
    )


@app.get("/sitemap.xml")
def sitemap():
    return Response(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        '<url><loc>https://razorpay-agentic-commerce-d5ii.onrender.com/</loc></url>'
        '</urlset>',
        media_type="application/xml",
    )


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


class NewProduct(BaseModel):
    name: str
    description: str = ""
    category: str = "general"
    price: float
    stock: int = 0


@app.post("/catalog/{merchant_id}/products")
def add_product(merchant_id: int, req: NewProduct, db: Session = Depends(get_session)):
    """Real catalog management, not fixed demo data - a merchant can add
    actual products the shopping agent will immediately be able to find."""
    product = Product(merchant_id=merchant_id, **req.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return {"id": product.id, "name": product.name, "price": product.price, "stock": product.stock}


class PrepareRequest(BaseModel):
    merchant_id: int
    buyer_agent_id: str
    query: str
    quantity: int = 1
    budget_limit: float | None = None
    authorized: bool = False


@app.post("/checkout/prepare")
def checkout_prepare(req: PrepareRequest, db: Session = Depends(get_session)):
    """Runs shop -> policy -> risk. If ready, also opens a real Razorpay
    checkout session (or the mock equivalent) for the frontend to use."""
    result = prepare_checkout(
        db, req.merchant_id, req.buyer_agent_id, req.query,
        req.quantity, req.budget_limit, req.authorized,
    )
    return {
        "order_id": result.order.id if result.order else None,
        "ready": result.ready,
        "status": result.status,
        "message": result.message,
        "checkout": result.checkout_session,
        "audit_trail": result.audit_trail,
    }


class ConfirmRequest(BaseModel):
    order_id: int
    preferred_method: str = "upi"
    razorpay_order_id: str | None = None
    razorpay_payment_id: str | None = None
    razorpay_signature: str | None = None


@app.post("/checkout/confirm")
def checkout_confirm(req: ConfirmRequest, db: Session = Depends(get_session)):
    """Confirms payment: real signature verification against Razorpay when
    live keys are configured, or the deterministic simulator otherwise."""
    order = db.get(Order, req.order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    payload = {
        "razorpay_order_id": req.razorpay_order_id,
        "razorpay_payment_id": req.razorpay_payment_id,
        "razorpay_signature": req.razorpay_signature,
    }
    result = finalize_payment(db, order, req.preferred_method, payload)
    return {
        "order_id": result.order_id,
        "status": result.status,
        "message": result.message,
        "audit_trail": result.audit_trail,
    }


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
