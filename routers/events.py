import os
import httpx
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession
from database import get_db
from models import User, Event
from dependencies import get_current_user

router = APIRouter(tags=["events"])

EVENTBRITE_TOKEN = os.getenv("EVENTBRITE_TOKEN", "")
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")

SEED_EVENTS = [
    {"title": "Austin City Limits Tapings", "description": "Live tapings of the iconic ACL show.", "category": "Music", "location": "ACL Studio, Austin, TX", "vibe_tags": ["music", "live-performances"]},
    {"title": "Emo's Big Summer Bash", "description": "Outdoor indie rock festival.", "category": "Music", "location": "Zilker Park, Austin, TX", "vibe_tags": ["music", "outdoor", "festival"]},
    {"title": "East Austin Studio Tour", "description": "Open studios of local artists.", "category": "Art", "location": "East Austin", "vibe_tags": ["art", "local", "free"]},
    {"title": "Food Park Friday Night", "description": "Rotating food trucks and live music.", "category": "Food", "location": "S. Congress Ave Food Park", "vibe_tags": ["food", "outdoor", "social"]},
    {"title": "Slackweed Yoga on the Lawn", "description": "Free community yoga session.", "category": "Outdoor", "location": "Zilker Metropolitan Park", "vibe_tags": ["outdoor", "wellness", "free"]},
    {"title": "Round Rock Express Baseball", "description": "Minor league baseball game.", "category": "Sports", "location": "Round Rock, TX", "vibe_tags": ["sports", "family", "affordable"]},
    {"title": "Tech Meetup Austin", "description": "Networking for startup founders.", "category": "Networking", "location": "Capital Factory, Downtown Austin", "vibe_tags": ["networking", "tech", "professional"]},
    {"title": "Blanton Museum Free Day", "description": "Free admission to the Blanton's collection.", "category": "Art", "location": "UT Campus", "vibe_tags": ["art", "free", "cultural"]},
    {"title": "Torchy's Tacos Trivia Night", "description": "Weekly trivia at Austin's favorite taco spot.", "category": "Food", "location": "Torchy's, various locations", "vibe_tags": ["food", "social", "free"]},
    {"title": "Lady Bird Lake Kayaking", "description": "Sunset paddleboarding on Lady Bird Lake.", "category": "Outdoor", "location": "Lady Bird Lake", "vibe_tags": ["outdoor", "active", "nature"]},
    {"title": "Mozart's Coffee Summer Concert", "description": "Acoustic performances in the garden.", "category": "Music", "location": "Mozart's Coffee, North Austin", "vibe_tags": ["music", "intimate", "coffee"]},
    {"title": "Rainey Street Block Party", "description": "Weekly street closure with bars and live music.", "category": "Social", "location": "Rainey Street", "vibe_tags": ["social", "nightlife", "outdoor"]},
    {"title": "Frontera Fund Farmers Market", "description": "Local produce and artisan goods.", "category": "Food", "location": "Republic Square Park", "vibe_tags": ["food", "local", "farmers-market"]},
    {"title": "Austin FC Soccer Match", "description": "MLS match at Q2 Stadium.", "category": "Sports", "location": "Q2 Stadium", "vibe_tags": ["sports", "soccer", "live-event"]},
    {"title": "Cactus Cafe Songwriter Night", "description": "Intimate singer-songwriter performances.", "category": "Music", "location": "UT Campus (Cactus Cafe)", "vibe_tags": ["music", "intimate", "songwriters"]},
    {"title": "Bat Watching at Congress Bridge", "description": "Watch the urban bat colony emerge.", "category": "Nature", "location": "Congress Bridge", "vibe_tags": ["nature", "free", "unique"]},
    {"title": "UT Longhorns Football Game", "description": "College football at Darrell K Royal Stadium.", "category": "Sports", "location": "UT Campus", "vibe_tags": ["sports", "college", "live-event"]},
    {"title": "Paddleboard Yoga", "description": "Yoga on the water.", "category": "Outdoor", "location": "Lady Bird Lake", "vibe_tags": ["outdoor", "wellness", "active"]},
    {"title": "Domain Art Walk", "description": "Gallery openings in the Domain.", "category": "Art", "location": "The Domain", "vibe_tags": ["art", "social", "nightlife"]},
    {"title": "Moonlight Tours at Mayfield Park", "description": "Evening nature walks and cottage tour.", "category": "Nature", "location": "Mayfield Park", "vibe_tags": ["nature", "free", "evening"]},
]

async def _fetch_eventbrite_events():
    if not EVENTBRITE_TOKEN:
        return []
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get("https://www.eventbriteapi.com/v3/events/search/", headers={"Authorization": f"Bearer {EVENTBRITE_TOKEN}"}, params={"location": {"city": "Austin", "country": "US"}, "start_date.keyword": "this_week", "limit": 50})
        if resp.status_code != 200:
            return []
        data = resp.json()
        return [{"title": e.get("name", {}).get("text", ""), "description": e.get("description", {}).get("text", "")[:500], "event_date": e.get("start", {}).get("utc"), "location": e.get("venue_id"), "category": "Event", "source_url": e.get("url"), "source_name": "Eventbrite"} for e in data.get("events", [])]
    except:
        return []

async def _fetch_reddit_events():
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        return []
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            token_resp = await client.post("https://www.reddit.com/api/v1/access_token", data={"grant_type": "client_credentials"}, auth=(REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET), headers={"User-Agent": "LocalPulse/1.0"})
            if token_resp.status_code != 200:
                return []
            token = token_resp.json().get("access_token")
            posts_resp = await client.get("https://oauth.reddit.com/r/Austin/search", headers={"Authorization": f"Bearer {token}", "User-Agent": "LocalPulse/1.0"}, params={"q": "event meetup concert festival", "limit": 25, "sort": "new"})
            if posts_resp.status_code != 200:
                return []
            posts = posts_resp.json()
            events = []
            for post in posts.get("data", {}).get("children", []):
                p = post.get("data", {})
                if any(k in p.get("title", "").lower() for k in ["meetup", "event", "festival", "concert", "show"]):
                    events.append({"title": p.get("title", "")[:200], "description": p.get("selftext", "")[:500], "event_date": None, "location": "Austin, TX", "category": "Community", "source_url": f"https://reddit.com{p.get('permalink', '')}", "source_name": "Reddit r/Austin"})
            return events
    except:
        return []

def _seed_events(db: DBSession):
    if db.query(Event).first():
        return
    now = datetime.utcnow()
    for i, e in enumerate(SEED_EVENTS):
        event = Event(title=e["title"], description=e["description"], event_date=now + timedelta(days=i+1), location=e["location"], category=e["category"], source_url="", source_name="seed", vibe_tags=e["vibe_tags"], is_last_minute=False)
        db.add(event)
    db.commit()

@router.get("/api/events")
async def list_events(limit: int = 50, category: str = None, db: DBSession = Depends(get_db), user: User = Depends(get_current_user)):
    _seed_events(db)
    query = db.query(Event).filter(Event.event_date > datetime.utcnow())
    if category:
        query = query.filter(Event.category == category)
    events = query.order_by(Event.event_date).limit(limit).all()
    return [{"id": str(e.id), "title": e.title, "description": e.description, "event_date": e.event_date.isoformat() if e.event_date else None, "location": e.location, "category": e.category, "source_url": e.source_url, "source_name": e.source_name, "vibe_tags": e.vibe_tags or []} for e in events]

@router.post("/api/events/aggregate")
async def trigger_aggregation(db: DBSession = Depends(get_db), user: User = Depends(get_current_user)):
    _seed_events(db)
    all_events = []
    all_events.extend(await _fetch_eventbrite_events())
    all_events.extend(await _fetch_reddit_events())
    for e in all_events:
        if e.get("source_url") and db.query(Event).filter(Event.source_url == e["source_url"]).first():
            continue
        event = Event(title=e.get("title", ""), description=e.get("description"), event_date=datetime.fromisoformat(e["event_date"].replace("Z", "+00:00")) if e.get("event_date") else datetime.utcnow() + timedelta(days=7), location=e.get("location"), category=e.get("category"), source_url=e.get("source_url", ""), source_name=e.get("source_name", "unknown"), is_last_minute=False)
        db.add(event)
    db.commit()
    return {"status": "completed", "total_events": db.query(Event).count()}