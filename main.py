import os
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import Base, engine
from routers import auth, quiz, digest, events, feedback, settings, payments

@asynccontextmanager
async def lifespan(app: FastAPI):
    for attempt in range(3):
        try:
            Base.metadata.create_all(bind=engine)
            break
        except Exception:
            if attempt < 2:
                time.sleep(2 ** attempt)
    yield

app = FastAPI(title="LocalPulse API", version="1.0.0", lifespan=lifespan)

origins = os.getenv("CORS_ORIGINS", os.getenv("FRONTEND_URL", "http://localhost:3000")).split(",")
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(auth.router)
app.include_router(quiz.router)
app.include_router(digest.router)
app.include_router(events.router)
app.include_router(feedback.router)
app.include_router(settings.router)
app.include_router(payments.router)

@app.get("/health")
async def health():
    return {"status": "ok"}
