from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession
from database import get_db
from models import User, TasteProfile
from schemas import TasteProfileCreate, TasteProfileResponse
from dependencies import get_current_user

router = APIRouter(tags=["quiz"])

@router.post("/api/quiz", response_model=TasteProfileResponse)
async def save_quiz(profile: TasteProfileCreate, user: User = Depends(get_current_user), db: DBSession = Depends(get_db)):
    existing = db.query(TasteProfile).filter_by(user_id=user.id).first()
    
    if existing:
        existing.event_types = profile.event_types
        existing.social_comfort = profile.social_comfort
        existing.budget_range = profile.budget_range
        existing.schedule_prefs = profile.schedule_prefs
        existing.neighborhood = profile.neighborhood
        existing.vibe_description = profile.vibe_description
    else:
        existing = TasteProfile(
            user_id=user.id,
            event_types=profile.event_types,
            social_comfort=profile.social_comfort,
            budget_range=profile.budget_range,
            schedule_prefs=profile.schedule_prefs,
            neighborhood=profile.neighborhood,
            vibe_description=profile.vibe_description,
        )
        db.add(existing)
    
    db.commit()
    db.refresh(existing)
    
    return TasteProfileResponse(
        id=str(existing.id),
        user_id=str(existing.user_id),
        event_types=existing.event_types or [],
        social_comfort=existing.social_comfort,
        budget_range=existing.budget_range,
        schedule_prefs=existing.schedule_prefs or [],
        neighborhood=existing.neighborhood,
        vibe_description=existing.vibe_description,
        updated_at=existing.updated_at,
    )

@router.get("/api/quiz", response_model=TasteProfileResponse)
async def get_quiz(user: User = Depends(get_current_user), db: DBSession = Depends(get_db)):
    profile = db.query(TasteProfile).filter_by(user_id=user.id).first()
    if not profile:
        raise HTTPException(404, detail="Taste profile not found")
    
    return TasteProfileResponse(
        id=str(profile.id),
        user_id=str(profile.user_id),
        event_types=profile.event_types or [],
        social_comfort=profile.social_comfort,
        budget_range=profile.budget_range,
        schedule_prefs=profile.schedule_prefs or [],
        neighborhood=profile.neighborhood,
        vibe_description=profile.vibe_description,
        updated_at=profile.updated_at,
    )
