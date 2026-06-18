import os
from fastapi import Depends, HTTPException, Cookie
from sqlalchemy.orm import Session as DBSession
from database import get_db
from models import User, UserSession
from datetime import datetime

def get_current_user(session_id: str | None = Cookie(None), db: DBSession = Depends(get_db)) -> User:
    if not session_id:
        raise HTTPException(401, detail="Not authenticated")
    session = db.query(UserSession).filter_by(id=session_id).first()
    if not session or session.expires_at < datetime.utcnow():
        if session:
            db.delete(session)
            db.commit()
        raise HTTPException(401, detail="Not authenticated")
    user = db.query(User).filter_by(id=session.user_id).first()
    if not user:
        raise HTTPException(401, detail="Not authenticated")
    return user

def get_user_subscription(db: DBSession, user_id: str):
    from models import Subscription
    sub = db.query(Subscription).filter_by(user_id=user_id).first()
    if not sub:
        return None
    return sub

def get_user_api_key(db: DBSession, user_id: str, service_name: str):
    from models import UserApiKey
    key = db.query(UserApiKey).filter_by(user_id=user_id, service_name=service_name).first()
    if not key:
        return None
    return key.api_key

def get_tier_limits(tier: str) -> dict:
    limits = {
        "free": {"max_events": 3, "has_email": False, "has_feedback": False, "has_history": False, "has_alerts": False, "max_digest_events": 3},
        "explorer": {"max_events": 10, "has_email": True, "has_feedback": True, "has_history": True, "has_alerts": False, "max_digest_events": 10},
        "local": {"max_events": 15, "has_email": True, "has_feedback": True, "has_history": True, "has_alerts": True, "max_digest_events": 15},
    }
    return limits.get(tier, limits["free"])
