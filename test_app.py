import sys
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("PADDLE_WEBHOOK_SECRET", "test-secret")

errors = []

try:
    import main as main_module
    app = main_module.app
    from fastapi import FastAPI
    assert isinstance(app, FastAPI), f"app is {type(app)}, not FastAPI"
except Exception as e:
    errors.append(f"APP_IMPORT: {e}")
    import traceback
    traceback.print_exc()
    print("FAILED"); [print(f"  {e}") for e in errors]; sys.exit(1)

try:
    spec = app.openapi()
    registered_paths = set()
    for path, methods in spec.get("paths", {}).items():
        for method in methods:
            if method.upper() not in ("HEAD", "OPTIONS"):
                registered_paths.add((method.upper(), path))
except Exception as e:
    errors.append(f"OPENAPI_ERROR: {e}")
    print("FAILED"); [print(f"  {e}") for e in errors]; sys.exit(1)

expected = [
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/logout"),
    ("GET", "/api/auth/me"),
    ("GET", "/api/auth/subscription"),
    ("POST", "/api/auth/verify-email"),
    ("POST", "/api/auth/resend-verification"),
    ("GET", "/api/quiz"),
    ("POST", "/api/quiz"),
    ("GET", "/api/digest/current"),
    ("GET", "/api/digest/history"),
    ("POST", "/api/digest/generate"),
    ("GET", "/api/events"),
    ("POST", "/api/events/aggregate"),
    ("POST", "/api/feedback"),
    ("GET", "/api/settings/keys"),
    ("PUT", "/api/settings/keys/{service_name}"),
    ("DELETE", "/api/settings/keys/{service_name}"),
    ("PUT", "/api/settings/alerts"),
    ("POST", "/api/payments/checkout"),
    ("POST", "/api/paddle/webhook"),
    ("POST", "/api/payments/verify-transaction"),
    ("GET", "/api/subscription/manage"),
    ("GET", "/health"),
]

for method, path in expected:
    if (method, path) not in registered_paths:
        errors.append(f"ROUTE_MISSING: {method} {path}")

modules_to_check = ["schemas", "dependencies", "ai_helpers", "routers.auth", "routers.quiz", "routers.digest", "routers.events", "routers.feedback", "routers.settings", "routers.payments"]
for mod in modules_to_check:
    try:
        __import__(mod)
    except Exception as e:
        errors.append(f"IMPORT_FAIL: {mod} -> {e}")

try:
    from sqlalchemy.orm import configure_mappers
    configure_mappers()
except Exception as e:
    errors.append(f"MAPPER_CONFIG: {e}")

if errors:
    print("FAILED")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)
print("PASSED")