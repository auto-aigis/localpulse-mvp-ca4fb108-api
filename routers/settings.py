import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession
from database import get_db
from models import User, UserApiKey, Subscription, AlertSubscription
from schemas import ApiKeyCreate, ApiKeyResponse, AlertsToggleRequest
from dependencies import get_current_user

router = APIRouter(tags=["settings"])

def _mask_key(key: str) -> str:
    if len(key) <= 6:
        return "***"
    return key[:3] + "***" + key[-3:]

@router.get("/api/settings/keys")
async def get_api_keys(user: User = Depends(get_current_user), db: DBSession = Depends(get_db)):
    keys = db.query(UserApiKey).filter_by(user_id=user.id).all()
    return [ApiKeyResponse(id=str(k.id), service_name=k.service_name, masked_key=_mask_key(k.api_key), created_at=k.created_at) for k in keys]

@router.put("/api/settings/keys/{service_name}")
async def upsert_api_key(service_name: str, key_data: ApiKeyCreate, user: User = Depends(get_current_user), db: DBSession = Depends(get_db)):
    if key_data.service_name != service_name:
        raise HTTPException(400, detail="Service name mismatch")
    existing = db.query(UserApiKey).filter_by(user_id=user.id, service_name=service_name).first()
    if existing:
        existing.api_key = key_data.api_key
    else:
        existing = UserApiKey(id=str(uuid.uuid4()), user_id=user.id, service_name=service_name, api_key=key_data.api_key)
        db.add(existing)
    db.commit()
    return {"status": "saved", "service": service_name}

@router.delete("/api/settings/keys/{service_name}")
async def delete_api_key(service_name: str, user: User = Depends(get_current_user), db: DBSession = Depends(get_db)):
    existing = db.query(UserApiKey).filter_by(user_id=user.id, service_name=service_name).first()
    if existing:
        db.delete(existing)
        db.commit()
    return {"status": "deleted"}

@router.put("/api/settings/alerts")
async def toggle_alerts(request: AlertsToggleRequest, user: User = Depends(get_current_user), db: DBSession = Depends(get_db)):
    sub = db.query(Subscription).filter_by(user_id=user.id).first()
    if not sub or sub.tier != "local":
        raise HTTPException(403, detail="Real-time alerts require Local tier")
    alert_sub = db.query(AlertSubscription).filter_by(user_id=user.id).first()
    if not alert_sub:
        alert_sub = AlertSubscription(user_id=user.id, opted_in=request.opted_in)
        db.add(alert_sub)
    else:
        alert_sub.opted_in = request.opted_in
    db.commit()
    return {"status": "updated", "opted_in": request.opted_in}