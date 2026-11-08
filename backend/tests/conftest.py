"""Shared test setup.

Unit tests need no database. Integration tests (tests/test_booking_flow.py)
run against a real PostgreSQL database when TEST_DATABASE_URL is set, and are
skipped otherwise. The CI pipeline provides one as a service container.
"""
import os

_TEST_DB = os.environ.get("TEST_DATABASE_URL")

# Settings are read when app modules are first imported, so set them here,
# before any test module imports the app.
os.environ.setdefault("DATABASE_URL", _TEST_DB or "postgresql+asyncpg://test:test@localhost/test")
if _TEST_DB:
    os.environ["DATABASE_URL"] = _TEST_DB
os.environ.setdefault("JWT_SECRET", "test-secret-for-tests-only")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_dummy")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_dummy")
os.environ.setdefault("RESEND_API_KEY", "re_test_dummy")
os.environ.setdefault("DAILY_API_KEY", "daily_test_dummy")
os.environ.setdefault("FRONTEND_URL", "https://test.example.com")
os.environ.setdefault("BACKGROUND_JOBS_ENABLED", "false")
