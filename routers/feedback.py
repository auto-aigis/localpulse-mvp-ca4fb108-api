import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession
from database import get_db
from models import User, EventFeedback, Subscription
from schemas import FeedbackCreate, FeedbackResponse
from dependencies import get_current_user, get_tier_limits

router = APIRouter(tags=["feedback"])

@router.post("/api/feedback", response_model=FeedbackResponse)
async def submit_feedback(feedback: FeedbackCreate, user: User = Depends(get_current_user), db: DBSession = Depends(get_db)):
    sub = db.query(Subscription).filter_by(user_id=user.id).first()
    tier = sub.tier if sub else "free"
    limits = get_tier_limits(tier)
    if not limits["has_feedback"]:
        raise HTTPException(403, detail="Feedback requires Explorer tier or higher")
    existing = db.query(EventFeedback).filter_by(user_id=user.id, event_id=feedback.event_id).first()
    if existing:
        existing.rating = feedback.rating
        existing.source = feedback.source
        db.commit()
        feedback_id = existing.id
    else:
        event_feedback = EventFeedback(id=str(uuid.uuid4()), user_id=user.id, event_id=feedback.event_id, digest_id=feedback.digest_id, rating=feedback.rating, source=feedback.source)
        db.add(event_feedback)
        db.commit()
        feedback_id = event_feedback.id
    return FeedbackResponse(id=feedback_id, user_id=str(user.id), event_id=str(feedback.event_id), rating=feedback.rating, source=feedback.source, created_at=datetime.utcnow())