import sys
import os
import secrets
from datetime import datetime
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")
os.environ.setdefault("PADDLE_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("RESEND_API_KEY", "test-key")
os.environ.setdefault("AI_GATEWAY_URL", "")

TEST_ENGINE = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=TEST_ENGINE, autoflush=False)

from database import Base, get_db
import main as main_module

Base.metadata.create_all(bind=TEST_ENGINE)

def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()

main_module.app.dependency_overrides[get_db] = override_get_db

client = TestClient(main_module.app, raise_server_exceptions=True)

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

def test_register_and_login(db):
    email = f"test-{secrets.token_hex(6)}@example.com"
    with patch("routers.auth._send_verification_email"):
        r = client.post("/api/auth/register", json={"email": email, "password": "TestPass123"})
    assert r.status_code == 200
    assert r.json()["status"] == "verification_sent"
    from models import User
    user = db.query(User).filter_by(email=email).first()
    user.is_email_verified = True
    db.commit()
    r = client.post("/api/auth/login", json={"email": email, "password": "TestPass123"})
    assert r.status_code == 200
    assert "session_id" in client.cookies

def test_invalid_login(db):
    r = client.post("/api/auth/login", json={"email": "nonexistent@example.com", "password": "wrong"})
    assert r.status_code == 401

def test_save_and_get_quiz(db):
    email = f"quiz-{secrets.token_hex(6)}@example.com"
    with patch("routers.auth._send_verification_email"):
        client.post("/api/auth/register", json={"email": email, "password": "TestPass123"})
    from models import User
    user = db.query(User).filter_by(email=email).first()
    user.is_email_verified = True
    db.commit()
    client.post("/api/auth/login", json={"email": email, "password": "TestPass123"})
    r = client.post("/api/quiz", json={"event_types": ["music", "food"], "social_comfort": "solo-friendly", "budget_range": "$15-$40", "schedule_prefs": ["weekends"], "neighborhood": "East Austin", "vibe_description": "Chill evenings"})
    assert r.status_code == 200
    r = client.get("/api/quiz")
    assert r.status_code == 200
    assert r.json()["event_types"] == ["music", "food"]

def test_subscription_default(db):
    email = f"sub-{secrets.token_hex(6)}@example.com"
    with patch("routers.auth._send_verification_email"):
        client.post("/api/auth/register", json={"email": email, "password": "TestPass123"})
    from models import User
    user = db.query(User).filter_by(email=email).first()
    user.is_email_verified = True
    db.commit()
    client.post("/api/auth/login", json={"email": email, "password": "TestPass123"})
    r = client.get("/api/auth/subscription")
    assert r.status_code == 200
    assert r.json()["tier"] == "free"

def test_feedback_requires_explorer(db):
    email = f"feedback-{secrets.token_hex(6)}@example.com"
    with patch("routers.auth._send_verification_email"):
        client.post("/api/auth/register", json={"email": email, "password": "TestPass123"})
    from models import User
    user = db.query(User).filter_by(email=email).first()
    user.is_email_verified = True
    db.commit()
    client.post("/api/auth/login", json={"email": email, "password": "TestPass123"})
    r = client.post("/api/feedback", json={"event_id": "test-123", "rating": "thumbs_up"})
    assert r.status_code == 403
