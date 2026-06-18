import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession
from database import get_db
from models import User, Subscription, TasteProfile, Event, Digest, DigestEvent, EventFeedback
from schemas import DigestResponse, CurrentDigestResponse, EventWithVibeResponse
from dependencies import get_current_user, get_tier_limits
from ai_helpers import generate_digest
import httpx

router = APIRouter(tags=["digest"])

PLATFORM_PAYMENT_WEBHOOK_URL = os.getenv("PLATFORM_PAYMENT_WEBHOOK_URL", "")
PROJECT_ID = os.getenv("PROJECT_ID", "localpulse")
PROJECT_SECRET = os.getenv("PROJECT_SECRET", "")

def _get_user_api_key(db: DBSession, user_id: str):
    from models import UserApiKey
    key = db.query(UserApiKey).filter_by(user_id=user_id, service_name="openai").first()
    return key.api_key if key else None

@router.get("/api/digest/current", response_model=CurrentDigestResponse)
async def get_current_digest(user: User = Depends(get_current_user), db: DBSession = Depends(get_db)):
    sub = db.query(Subscription).filter_by(user_id=user.id).first()
    tier = sub.tier if sub else "free"
    limits = get_tier_limits(tier)
    
    latest_digest = db.query(Digest).filter_by(user_id=user.id).order_by(Digest.generated_at.desc()).first()
    
    if not latest_digest:
        return CurrentDigestResponse(
            digest=None,
            subscription_tier=tier,
            can_upgrade=tier == "free",
        )
    
    digest_events = db.query(DigestEvent).filter_by(digest_id=latest_digest.id).order_by(DigestEvent.rank_order).all()
    
    events = []
    for de in digest_events[:limits["max_events"]]:
        event = db.query(Event).filter_by(id=de.event_id).first()
        if event:
            events.append(EventWithVibeResponse(
                id=str(event.id),
                title=event.title,
                event_date=event.event_date,
                location=event.location,
                category=event.category,
                source_url=event.source_url,
                ai_vibe_description=de.ai_vibe_description,
                rank_order=de.rank_order,
            ))
    
    digest_response = DigestResponse(
        id=str(latest_digest.id),
        user_id=str(latest_digest.user_id),
        generated_at=latest_digest.generated_at,
        events=events,
        tier_snapshot=latest_digest.tier_snapshot,
        is_email_sent=latest_digest.is_email_sent,
    )
    
    return CurrentDigestResponse(
        digest=digest_response,
        subscription_tier=tier,
        can_upgrade=tier == "free" and latest_digest is not None,
    )

@router.get("/api/digest/history", response_model=list[dict])
async def get_digest_history(user: User = Depends(get_current_user), db: DBSession = Depends(get_db)):
    sub = db.query(Subscription).filter_by(user_id=user.id).first()
    tier = sub.tier if sub else "free"
    limits = get_tier_limits(tier)
    
    if not limits["has_history"]:
        raise HTTPException(403, detail="Digest history requires Explorer tier or higher")
    
    digests = db.query(Digest).filter_by(user_id=user.id).order_by(Digest.generated_at.desc()).limit(20).all()
    
    result = []
    for d in digests:
        digest_events = db.query(DigestEvent).filter_by(digest_id=d.id).order_by(DigestEvent.rank_order).all()
        events = []
        for de in digest_events:
            event = db.query(Event).filter_by(id=de.event_id).first()
            if event:
                events.append({
                    "id": str(event.id),
                    "title": event.title,
                    "event_date": event.event_date.isoformat() if event.event_date else None,
                    "location": event.location,
                    "category": event.category,
                    "ai_vibe_description": de.ai_vibe_description,
                })
        result.append({
            "id": str(d.id),
            "generated_at": d.generated_at.isoformat(),
            "events": events,
            "tier_snapshot": d.tier_snapshot,
        })
    
    return result

@router.post("/api/digest/generate", response_model=DigestResponse)
async def generate_new_digest(user: User = Depends(get_current_user), db: DBSession = Depends(get_db)):
    profile = db.query(TasteProfile).filter_by(user_id=user.id).first()
    if not profile:
        raise HTTPException(400, detail="Please complete the taste quiz first")
    
    sub = db.query(Subscription).filter_by(user_id=user.id).first()
    tier = sub.tier if sub else "free"
    limits = get_tier_limits(tier)
    
    now = datetime.utcnow()
    events = db.query(Event).filter(Event.event_date > now).order_by(Event.event_date).limit(100).all()
    
    if not events:
        raise HTTPException(400, detail="No events available. Please try again later.")
    
    feedback = []
    fb_records = db.query(EventFeedback).filter_by(user_id=user.id).all()
    for f in fb_records:
        event = db.query(Event).filter_by(id=f.event_id).first()
        if event:
            feedback.append({"event": event, "rating": f.rating})
    
    api_key = _get_user_api_key(db, user.id)
    
    try:
        digest_events_data = await generate_digest(
            events=[{
                "event_id": e.id,
                "title": e.title,
                "description": e.description,
                "event_date": e.event_date.isoformat() if e.event_date else None,
                "location": e.location,
                "category": e.category,
                "source_url": e.source_url,
                "vibe_tags": e.vibe_tags or [],
            } for e in events],
            taste_profile={
                "event_types": profile.event_types or [],
                "social_comfort": profile.social_comfort,
                "budget_range": profile.budget_range,
                "schedule_prefs": profile.schedule_prefs or [],
                "neighborhood": profile.neighborhood,
                "vibe_description": profile.vibe_description,
            },
            feedback=feedback,
            max_events=limits["max_digest_events"],
            api_key=api_key,
        )
    except Exception as e:
        print(f"Digest generation failed: {e}")
        raise HTTPException(500, detail="Failed to generate digest")
    
    digest = Digest(
        user_id=user.id,
        tier_snapshot=tier,
        is_email_sent=False,
    )
    db.add(digest)
    db.commit()
    db.refresh(digest)
    
    events_response = []
    for i, de_data in enumerate(digest_events_data):
        event_row = db.query(Event).filter_by(id=de_data.get("event_id")).first()
        if not event_row:
            event_row = db.query(Event).filter(Event.title == de_data.get("title")).first()
        
        if not event_row:
            continue
        
        digest_event = DigestEvent(
            digest_id=digest.id,
            event_id=event_row.id,
            ai_vibe_description=de_data.get("ai_vibe_description", "Check out this event!"),
            rank_order=i + 1,
        )
        db.add(digest_event)
        
        events_response.append(EventWithVibeResponse(
            id=str(event_row.id),
            title=event_row.title,
            event_date=event_row.event_date,
            location=event_row.location,
            category=event_row.category,
            source_url=event_row.source_url,
            ai_vibe_description=digest_event.ai_vibe_description,
            rank_order=i + 1,
        ))
    
    db.commit()
    
    return DigestResponse(
        id=str(digest.id),
        user_id=str(digest.user_id),
        generated_at=digest.generated_at,
        events=events_response,
        tier_snapshot=tier,
        is_email_sent=digest.is_email_sent,
    )
