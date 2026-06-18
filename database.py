import os
import re
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

if db_url and os.getenv("RENDER"):
    db_url = re.sub(r"(dpg-[a-z0-9-]+)\.[a-z.-]*render\.com", r"\1", db_url)
    db_url = re.sub(r"[?&]sslmode=[^&]*", "", db_url)

if db_url and "postgresql" in db_url:
    engine = create_engine(db_url, pool_pre_ping=True, pool_recycle=300, pool_size=3, max_overflow=5, pool_timeout=30)
else:
    engine = create_engine("sqlite:///:memory:")

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
