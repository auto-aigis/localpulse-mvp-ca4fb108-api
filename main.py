import os
import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from database import Base, engine
from routers import auth, quiz, digest, events, feedback, settings, payments

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cors_debug")


class CORSDebugMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin", "<no origin>")
        if request.method == "OPTIONS":
            logger.info(
                "PREFLIGHT | origin=%s | path=%s | allowed_origins=%s",
                origin,
                request.url.path,
                os.getenv("CORS_ORIGINS", os.getenv("FRONTEND_URL", "http://localhost:3000")),
            )
        response = await call_next(request)
        if request.method == "OPTIONS":
            logger.info(
                "PREFLIGHT RESPONSE | origin=%s | status=%s | access-control-allow-origin=%s",
                origin,
                response.status_code,
                response.headers.get("access-control-allow-origin", "<not set>"),
            )
        return response


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
origins = [o.strip().rstrip("/") for o in origins]
logger.info("CORS allowed origins at startup: %s", origins)

app.add_middleware(CORSDebugMiddleware)
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
