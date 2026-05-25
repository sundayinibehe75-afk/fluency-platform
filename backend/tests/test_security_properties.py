"""Property-based tests for authentication security functions.

Feature: fluency-platform-upgrade

Property 4: Password hashing correctness
  For any plaintext password >= 8 chars, verify_password(plain, hash_password(plain))
  is True and hash_password(plain) != plain.
  Validates: Requirements 13.1

Property 5: JWT claims round-trip
  For any (id, email, role) triple, decode_access_token(create_access_token(...))
  returns equal claims and exp - iat == 86400.
  Validates: Requirements 1.5, 1.8
"""
import os
import uuid

import pytest
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

# Set a dummy JWT_SECRET so config can be loaded without a real .env
os.environ.setdefault("JWT_SECRET", "test-secret-for-property-tests-only")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_dummy")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_dummy")
os.environ.setdefault("RESEND_API_KEY", "re_dummy")
os.environ.setdefault("DAILY_API_KEY", "daily_dummy")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")

from app.core.security import (  # noqa: E402
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

# Use a lower bcrypt cost factor in tests so the suite runs fast.
# The correctness property (hash → verify round-trip) is independent of cost.
import app.core.security as _security_module
_security_module._BCRYPT_ROUNDS = 4

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Passwords: printable ASCII only (single-byte chars), length 8–64.
# Restricted to ASCII to stay safely under bcrypt's 72-byte limit.
_password_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters="!@#$%^&*()-_=+[]{}|;:,.<>?/`~",
        blacklist_categories=("Cs",),
    ),
    min_size=8,
    max_size=64,
).filter(lambda s: len(s.encode("utf-8")) <= 72)

# Valid email-like strings (simple, not full RFC 5321)
_email_strategy = st.emails()

# Roles
_role_strategy = st.sampled_from(["student", "tutor", "admin"])

# UUIDs
_uuid_strategy = st.uuids()


# ---------------------------------------------------------------------------
# Property 4: Password hashing correctness
# Validates: Requirements 13.1
# ---------------------------------------------------------------------------


@given(plain=_password_strategy)
@h_settings(max_examples=20, deadline=None)
def test_password_hashing_correctness(plain: str) -> None:
    """**Property 4: Password hashing correctness**

    For any plaintext password >= 8 chars:
    1. verify_password(plain, hash_password(plain)) is True
    2. hash_password(plain) != plain  (hash is never stored as plaintext)

    **Validates: Requirements 13.1**
    """
    hashed = hash_password(plain)

    # The hash must verify correctly against the original plaintext
    assert verify_password(plain, hashed), (
        f"verify_password returned False for plain={plain!r}"
    )

    # The stored hash must never equal the plaintext
    assert hashed != plain, (
        f"hash_password returned the plaintext unchanged for plain={plain!r}"
    )


# ---------------------------------------------------------------------------
# Property 5: JWT claims round-trip
# Validates: Requirements 1.5, 1.8
# ---------------------------------------------------------------------------


@given(
    user_id=_uuid_strategy,
    email=_email_strategy,
    role=_role_strategy,
)
@h_settings(max_examples=20)
def test_jwt_claims_round_trip(user_id: uuid.UUID, email: str, role: str) -> None:
    """**Property 5: JWT claims round-trip**

    For any (id, email, role) triple:
    1. decode_access_token(create_access_token(...)) returns equal claims
    2. exp - iat == 86400 (exactly 24 hours)

    **Validates: Requirements 1.5, 1.8**
    """
    token = create_access_token(user_id, email, role)
    payload = decode_access_token(token)

    # sub claim must equal the user_id (as string)
    assert payload["sub"] == str(user_id), (
        f"sub mismatch: expected {str(user_id)!r}, got {payload['sub']!r}"
    )

    # email claim must round-trip exactly
    assert payload["email"] == email, (
        f"email mismatch: expected {email!r}, got {payload['email']!r}"
    )

    # role claim must round-trip exactly
    assert payload["role"] == role, (
        f"role mismatch: expected {role!r}, got {payload['role']!r}"
    )

    # jti must be present and non-empty
    assert payload.get("jti"), "jti claim is missing or empty"

    # exp - iat must be exactly 86400 seconds (24 hours)
    iat: int = payload["iat"]
    exp: int = payload["exp"]
    assert exp - iat == 86_400, (
        f"exp - iat = {exp - iat}, expected 86400"
    )
