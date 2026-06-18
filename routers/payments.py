import os
import hmac
import hashlib
import json
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session as DBSession
from database import get_db
from models import User, Subscription
from schemas import CheckoutRequest, CheckoutResponse, VerifyTransactionRequest, VerifyTransactionResponse
from dependencies import get_current_user

router = APIRouter(tags=["payments"])

PADDLE_API_KEY = os.getenv("PADDLE_API_KEY", "")
PADDLE_CLIENT_TOKEN = os.getenv("PADDLE_CLIENT_TOKEN", "")
PADDLE_WEBHOOK_SECRET = os.getenv("PADDLE_WEBHOOK_SECRET", "")
PADDLE_ENVIRONMENT = os.getenv("PADDLE_ENVIRONMENT", "sandbox")
PLATFORM_PAYMENT_WEBHOOK_URL = os.getenv("PLATFORM_PAYMENT_WEBHOOK_URL", "")
PROJECT_ID = os.getenv("PROJECT_ID", "localpulse")
PROJECT_SECRET = os.getenv("PROJECT_SECRET", "")

PADDLE_PRICE_IDS = {
    ("explorer", "monthly"): os.getenv("PADDLE_PRICE_ID_EXPLORER_MONTHLY", ""),
    ("explorer", "yearly"): os.getenv("PADDLE_PRICE_ID_EXPLORER_YEARLY", ""),
    ("local", "monthly"): os.getenv("PADDLE_PRICE_ID_LOCAL_MONTHLY", ""),
    ("local", "yearly"): os.getenv("PADDLE_PRICE_ID_LOCAL_YEARLY", ""),
}

PADDLE_BASE_URL = "https://sandbox-api.paddle.com" if PADDLE_ENVIRONMENT == "sandbox" else "https://api.paddle.com"

def _get_tier_from_price_id(price_id: str) -> str:
    price_map = {
        os.getenv("PADDLE_PRICE_ID_EXPLORER_MONTHLY", ""): "explorer",
        os.getenv("PADDLE_PRICE_ID_EXPLORER_YEARLY", ""): "explorer",
        os.getenv("PADDLE_PRICE_ID_LOCAL_MONTHLY", ""): "local",
        os.getenv("PADDLE_PRICE_ID_LOCAL_YEARLY", ""): "local",
    }
    return price_map.get(price_id, "free")

@router.post("/api/payments/checkout", response_model=CheckoutResponse)
async def create_checkout(req: CheckoutRequest, user: User = Depends(get_current_user)):
    tier = req.tier.lower()
    interval = req.billing_interval.lower()
    price_id = PADDLE_PRICE_IDS.get((tier, interval), "")
    if not price_id:
        raise HTTPException(400, detail="Invalid tier or pricing not configured")
    return CheckoutResponse(price_id=price_id, client_token=PADDLE_CLIENT_TOKEN)

@router.get("/api/subscription/manage")
async def get_paddle_portal(user: User = Depends(get_current_user), db: DBSession = Depends(get_db)):
    sub = db.query(Subscription).filter_by(user_id=user.id).first()
    if not sub or not sub.paddle_subscription_id:
        raise HTTPException(400, detail="No active subscription")
    portal_url = f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/settings?tab=subscription"
    return {"url": portal_url}

@router.post("/api/paddle/webhook")
async def paddle_webhook(request: Request, db: DBSession = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("Paddle-Signature", "")
    if not PADDLE_WEBHOOK_SECRET:
        raise HTTPException(500, detail="Webhook secret not configured")
    ts, h1 = "", ""
    for part in signature.split(";"):
        if part.startswith("ts="):
            ts = part[3:]
        elif part.startswith("h1="):
            h1 = part[3:]
    if not ts or not h1:
        raise HTTPException(400, detail="Invalid signature format")
    expected = hmac.new(PADDLE_WEBHOOK_SECRET.encode(), f"{ts}:{body.decode()}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, h1):
        raise HTTPException(401, detail="Invalid signature")
    try:
        data = json.loads(body)
    except:
        raise HTTPException(400, detail="Invalid JSON")
    event_type = data.get("event_type", "")
    if event_type in ("subscription.created", "subscription.activated", "subscription.updated"):
        subscription = data.get("data", {}).get("subscription", {})
        customer_id, sub_id, status = subscription.get("customer_id"), subscription.get("id"), subscription.get("status")
        items = subscription.get("items", [])
        price_id = items[0]["price"]["id"] if items else None
        billing_interval = items[0]["billing_cycle"] if items else None
        user_id = subscription.get("custom_data", {}).get("user_id")
        if user_id:
            user = db.query(User).filter_by(id=user_id).first()
            if user:
                sub = db.query(Subscription).filter_by(user_id=user.id).first()
                if not sub:
                    sub = Subscription(user_id=user.id)
                    db.add(sub)
                sub.paddle_customer_id = customer_id
                sub.paddle_subscription_id = sub_id
                sub.status = status
                sub.price_id = price_id
                sub.tier = _get_tier_from_price_id(price_id) if price_id else "free"
                sub.billing_interval = billing_interval
                db.commit()
    elif event_type == "subscription.canceled":
        subscription = data.get("data", {}).get("subscription", {})
        sub_id = subscription.get("id")
        sub = db.query(Subscription).filter_by(paddle_subscription_id=sub_id).first()
        if sub:
            sub.status = "canceled"
            sub.tier = "free"
            db.commit()
    elif event_type == "transaction.completed":
        transaction = data.get("data", {}).get("transaction", {})
        user_id = transaction.get("custom_data", {}).get("user_id")
        amount = transaction.get("amount", {})
        if user_id and PLATFORM_PAYMENT_WEBHOOK_URL:
            try:
                httpx.post(PLATFORM_PAYMENT_WEBHOOK_URL, json={"project_id": PROJECT_ID, "secret": PROJECT_SECRET, "amount": amount.get("total", 0)}, timeout=10)
            except Exception as e:
                print(f"Payment webhook failed: {e}")
    return {"status": "received"}

@router.post("/api/payments/verify-transaction", response_model=VerifyTransactionResponse)
async def verify_transaction(req: VerifyTransactionRequest, user: User = Depends(get_current_user), db: DBSession = Depends(get_db)):
    if not PADDLE_API_KEY:
        raise HTTPException(500, detail="Paddle not configured")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{PADDLE_BASE_URL}/transactions/{req.transaction_id}", headers={"Authorization": f"Bearer {PADDLE_API_KEY}"})
        resp.raise_for_status()
    except:
        raise HTTPException(400, detail="Failed to verify transaction")
    transaction = resp.json().get("data", {})
    status = transaction.get("status")
    if status not in ("completed", "paid"):
        raise HTTPException(400, detail="Transaction not completed")
    items = transaction.get("items", [])
    price_id = items[0]["price"]["id"] if items else None
    tier = _get_tier_from_price_id(price_id)
    sub = db.query(Subscription).filter_by(user_id=user.id).first()
    if not sub:
        sub = Subscription(user_id=user.id)
        db.add(sub)
    sub.status = "active"
    sub.tier = tier
    sub.price_id = price_id
    db.commit()
    return VerifyTransactionResponse(status="active", tier=tier)