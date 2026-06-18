import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, ForeignKey, ARRAY, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(255))
    is_email_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    taste_profile = relationship("TasteProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    digests = relationship("Digest", back_populates="user", cascade="all, delete-orphan")
    feedback = relationship("EventFeedback", back_populates="user", cascade="all, delete-orphan")
    api_keys = relationship("UserApiKey", back_populates="user", cascade="all, delete-orphan")
    alert_subscriptions = relationship("AlertSubscription", back_populates="user", uselist=False, cascade="all, delete-orphan")

class UserSession(Base):
    __tablename__ = "user_sessions"
    
    id = Column(String(64), primary_key=True, default=lambda: __import__('secrets').token_urlsafe(48))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", backref="sessions")

class EmailVerification(Base):
    __tablename__ = "email_verifications"
    
    id = Column(String(64), primary_key=True, default=lambda: __import__('secrets').token_urlsafe(48))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", backref="verification_tokens")

class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    paddle_customer_id = Column(String(255))
    paddle_subscription_id = Column(String(255), unique=True)
    status = Column(String(50), default="inactive")
    price_id = Column(String(255))
    tier = Column(String(50), default="free")
    billing_interval = Column(String(50))
    current_period_end = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="subscriptions")

class TasteProfile(Base):
    __tablename__ = "taste_profiles"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    event_types = Column(ARRAY(String), default=[])
    social_comfort = Column(String(50))
    budget_range = Column(String(50))
    schedule_prefs = Column(ARRAY(String), default=[])
    neighborhood = Column(String(255), default="Austin, TX")
    vibe_description = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="taste_profile")

class Event(Base):
    __tablename__ = "events"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(500), nullable=False)
    description = Column(Text)
    event_date = Column(DateTime, nullable=False)
    location = Column(String(500))
    category = Column(String(100))
    source_url = Column(String(1000))
    source_name = Column(String(100))
    vibe_tags = Column(ARRAY(String), default=[])
    is_last_minute = Column(Boolean, default=False)
    raw_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    digest_events = relationship("DigestEvent", back_populates="event")
    feedback = relationship("EventFeedback", back_populates="event")

class Digest(Base):
    __tablename__ = "digests"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow)
    event_ids = Column(ARRAY(String), default=[])
    tier_snapshot = Column(String(50))
    is_email_sent = Column(Boolean, default=False)
    
    user = relationship("User", back_populates="digests")
    digest_events = relationship("DigestEvent", back_populates="digest", cascade="all, delete-orphan")

class DigestEvent(Base):
    __tablename__ = "digest_events"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    digest_id = Column(String(36), ForeignKey("digests.id", ondelete="CASCADE"), index=True, nullable=False)
    event_id = Column(String(36), ForeignKey("events.id", ondelete="CASCADE"), index=True, nullable=False)
    ai_vibe_description = Column(Text)
    rank_order = Column(Integer)
    
    digest = relationship("Digest", back_populates="digest_events")
    event = relationship("Event", back_populates="digest_events")

class EventFeedback(Base):
    __tablename__ = "event_feedback"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    event_id = Column(String(36), ForeignKey("events.id", ondelete="CASCADE"), index=True, nullable=False)
    digest_id = Column(String(36), ForeignKey("digests.id", ondelete="CASCADE"), index=True)
    rating = Column(String(20))
    source = Column(String(20), default="web")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="feedback")
    event = relationship("Event", back_populates="feedback")
    digest = relationship("Digest")

class UserApiKey(Base):
    __tablename__ = "user_api_keys"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    service_name = Column(String(100), nullable=False)
    api_key = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="api_keys")
    __table_args__ = (
        UniqueConstraint('user_id', 'service_name', name='uq_user_service'),
    )

class AlertSubscription(Base):
    __tablename__ = "alert_subscriptions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    opted_in = Column(Boolean, default=True)
    last_alerted_at = Column(DateTime)
    
    user = relationship("User", back_populates="alert_subscriptions")
