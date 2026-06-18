import os
import secrets
from datetime import datetime, timedelta
import httpx
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.orm import Session as DBSession
import bcrypt
from database import get_db
from models import User, UserSession, EmailVerification, Subscription
from schemas import LoginRequest, RegisterRequest, UserResponse, VerifyEmailRequest, ResendVerificationRequest, SubscriptionResponse
from dependencies import get_current_user

router = APIRouter(tags=["auth"])

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
PLATFORM_WEBHOOK_URL = os.getenv("PLATFORM_WEBHOOK_URL", "")
PROJECT_ID = os.getenv("PROJECT_ID", "localpulse")
PROJECT_SECRET = os.getenv("PROJECT_SECRET", "")

def _send_verification_email(email: str, token: str):
    if not RESEND_API_KEY:
        return
    import resend
    resend.api_key = RESEND_API_KEY
    verify_url = f"{FRONTEND_URL}/verify-email?token={token}"
    
    html_content = f"""
    <div style="font-family: Georgia, serif; max-width: 600px; margin: 0 auto; padding: 40px 20px;">
        <h1 style="color: #2d5a4a; margin-bottom: 24px;">Welcome to LocalPulse!</h1>
        <p style="font-size: 18px; line-height: 1.6; color: #333;">
            Thanks for signing up. Click the button below to verify your email and get your first personalized event digest.
        </p>
        <a href="{verify_url}" style="display: inline-block; background: #c45a3b; color: white; padding: 16px 32px; text-decoration: none; border-radius: 4px; margin: 24px 0; font-weight: bold;">
            Verify Email
        </a>
        <p style="color: #666; font-size: 14px;">
            If you didn't sign up for LocalPulse, you can safely ignore this email.
        </p>
    </div>
    """
    
    try:
        resend.Emails.send({
            "from": "LocalPulse <noreply@localpulse.app>",
            "to": email,
            "subject": "Verify your email for LocalPulse",
            "html": html_content,
        })
    except Exception as e:
        print(f"Failed to send verification email: {e}")

@router.post("/api/auth/register", status_code=200)
async def register(req: RegisterRequest, response: Response, db: DBSession = Depends(get_db)):
    existing = db.query(User).filter_by(email=req.email).first()
    if existing:
        raise HTTPException(400, detail="Email already registered")
    
    password_hash = _hash_password(req.password)
    user = User(
        email=req.email,
        password_hash=password_hash,
        display_name=req.display_name,
        is_email_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    token = secrets.token_urlsafe(48)
    verification = EmailVerification(
        id=token,
        user_id=user.id,
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    db.add(verification)
    db.commit()
    
    try:
        _send_verification_email(req.email, token)
    except Exception as e:
        print(f"Email send failed: {e}")
    
    if PLATFORM_WEBHOOK_URL:
        try:
            httpx.post(PLATFORM_WEBHOOK_URL, json={
                "project_id": PROJECT_ID,
                "secret": PROJECT_SECRET,
            }, timeout=10)
        except Exception as e:
            print(f"Platform webhook failed: {e}")
    
    return {"status": "verification_sent", "email": user.email}

@router.post("/api/auth/login")
async def login(req: LoginRequest, response: Response, db: DBSession = Depends(get_db)):
    user = db.query(User).filter_by(email=req.email).first()
    if not user or not _verify_password(req.password, user.password_hash):
        raise HTTPException(401, detail="Invalid credentials")
    
    if not user.is_email_verified:
        raise HTTPException(403, detail="email_not_verified")
    
    session_token = secrets.token_urlsafe(48)
    session = UserSession(
        id=session_token,
        user_id=user.id,
        expires_at=datetime.utcnow() + timedelta(days=7),
    )
    db.add(session)
    db.commit()
    
    response.set_cookie("session_id", session_token, httponly=True, samesite="none", secure=True, max_age=7*86400)
    
    return UserResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        is_email_verified=user.is_email_verified,
        created_at=user.created_at,
    )

@router.post("/api/auth/logout")
async def logout(request: Request, response: Response, user: User = Depends(get_current_user), db: DBSession = Depends(get_db)):
    session_id = request.cookies.get("session_id")
    if session_id:
        session = db.query(UserSession).filter_by(id=session_id).first()
        if session:
            db.delete(session)
            db.commit()
    
    response.delete_cookie("session_id")
    return {"status": "logged_out"}

@router.get("/api/auth/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return UserResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        is_email_verified=user.is_email_verified,
        created_at=user.created_at,
    )

@router.get("/api/auth/subscription", response_model=SubscriptionResponse)
async def get_subscription(user: User = Depends(get_current_user), db: DBSession = Depends(get_db)):
    sub = db.query(Subscription).filter_by(user_id=user.id).first()
    if not sub:
        sub = Subscription(user_id=user.id, tier="free", status="inactive")
        db.add(sub)
        db.commit()
        db.refresh(sub)
    
    return SubscriptionResponse(
        id=str(sub.id),
        tier=sub.tier,
        status=sub.status,
        billing_interval=sub.billing_interval,
        current_period_end=sub.current_period_end,
    )

@router.post("/api/auth/verify-email")
async def verify_email(req: VerifyEmailRequest, response: Response, db: DBSession = Depends(get_db)):
    verification = db.query(EmailVerification).filter_by(id=req.token).first()
    if not verification or verification.expires_at < datetime.utcnow():
        raise HTTPException(400, detail="Invalid or expired token")
    
    user = db.query(User).filter_by(id=verification.user_id).first()
    if not user:
        raise HTTPException(404, detail="User not found")
    
    user.is_email_verified = True
    db.delete(verification)
    
    if not db.query(Subscription).filter_by(user_id=user.id).first():
        sub = Subscription(user_id=user.id, tier="free", status="inactive")
        db.add(sub)
    
    db.commit()
    
    session_token = secrets.token_urlsafe(48)
    session = UserSession(
        id=session_token,
        user_id=user.id,
        expires_at=datetime.utcnow() + timedelta(days=7),
    )
    db.add(session)
    db.commit()
    
    response.set_cookie("session_id", session_token, httponly=True, samesite="none", secure=True, max_age=7*86400)
    
    return {"status": "verified"}

@router.post("/api/auth/resend-verification")
async def resend_verification(req: ResendVerificationRequest, db: DBSession = Depends(get_db)):
    user = db.query(User).filter_by(email=req.email).first()
    if not user:
        return {"status": "sent"}
    
    db.query(EmailVerification).filter_by(user_id=user.id).delete()
    
    token = secrets.token_urlsafe(48)
    verification = EmailVerification(
        id=token,
        user_id=user.id,
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    db.add(verification)
    db.commit()
    
    try:
        _send_verification_email(req.email, token)
    except Exception as e:
        print(f"Email send failed: {e}")
    
    return {"status": "sent"}
