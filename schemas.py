from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: Optional[str] = None

class VerifyEmailRequest(BaseModel):
    token: str

class ResendVerificationRequest(BaseModel):
    email: EmailStr

class UserResponse(BaseModel):
    id: str
    email: str
    display_name: Optional[str] = None
    is_email_verified: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class SubscriptionResponse(BaseModel):
    id: str
    tier: str
    status: str
    billing_interval: Optional[str] = None
    current_period_end: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class TasteProfileCreate(BaseModel):
    event_types: List[str] = []
    social_comfort: Optional[str] = None
    budget_range: Optional[str] = None
    schedule_prefs: List[str] = []
    neighborhood: str = "Austin, TX"
    vibe_description: Optional[str] = None

class TasteProfileResponse(BaseModel):
    id: str
    user_id: str
    event_types: List[str] = []
    social_comfort: Optional[str] = None
    budget_range: Optional[str] = None
    schedule_prefs: List[str] = []
    neighborhood: str = "Austin, TX"
    vibe_description: Optional[str] = None
    updated_at: datetime
    
    class Config:
        from_attributes = True

class EventResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    event_date: datetime
    location: Optional[str] = None
    category: Optional[str] = None
    source_url: Optional[str] = None
    source_name: Optional[str] = None
    vibe_tags: List[str] = []
    is_last_minute: bool = False
    
    class Config:
        from_attributes = True

class EventWithVibeResponse(BaseModel):
    id: str
    title: str
    event_date: datetime
    location: Optional[str] = None
    category: Optional[str] = None
    source_url: Optional[str] = None
    ai_vibe_description: Optional[str] = None
    rank_order: Optional[int] = None

class DigestResponse(BaseModel):
    id: str
    user_id: str
    generated_at: datetime
    events: List[EventWithVibeResponse] = []
    tier_snapshot: Optional[str] = None
    is_email_sent: bool = False
    
    class Config:
        from_attributes = True

class CurrentDigestResponse(BaseModel):
    digest: Optional[DigestResponse] = None
    subscription_tier: str = "free"
    can_upgrade: bool = True

class FeedbackCreate(BaseModel):
    event_id: str
    digest_id: Optional[str] = None
    rating: str = Field(..., pattern=r"^(thumbs_up|thumbs_down|1|2|3|4|5)$")
    source: str = "web"

class FeedbackResponse(BaseModel):
    id: str
    user_id: str
    event_id: str
    rating: str
    source: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class ApiKeyCreate(BaseModel):
    service_name: str = Field(..., pattern=r"^(openai|anthropic|google)$")
    api_key: str

class ApiKeyResponse(BaseModel):
    id: str
    service_name: str
    masked_key: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class AlertsToggleRequest(BaseModel):
    opted_in: bool

class CheckoutRequest(BaseModel):
    tier: str = Field(..., pattern=r"^(explorer|local)$")
    billing_interval: str = Field(..., pattern=r"^(monthly|yearly)$")

class CheckoutResponse(BaseModel):
    price_id: str
    client_token: str

class VerifyTransactionRequest(BaseModel):
    transaction_id: str

class VerifyTransactionResponse(BaseModel):
    status: str
    tier: Optional[str] = None
