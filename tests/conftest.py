import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")
os.environ.setdefault("PADDLE_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("AI_GATEWAY_URL", "")