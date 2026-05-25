"""Auth router — five authentication endpoints with rate limiting.

Endpoints:
- POST /auth/register                — create student account, return JWT
- POST /auth/login                   — verify credentials, return JWT
- POST /auth/logout                  — invalidate JWT (add JTI to denylist)
- POST /auth/reset-password/request  — send password reset email
- POST /auth/reset-password/confirm  — apply new password, invalidate token

Rate limiting (slowapi): max 10 requests / 60 s per IP on /login and /register.
All error responses use the format: {"error": "ERROR_CODE", "detail": "message"}.
"""
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    ResetPasswordConfirmBody,
    ResetPasswordRequestBody,
    TokenResponse,
)
from app.services import auth_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate limiter — shared limiter instance (in-memory, per-IP)
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)

_bearer_scheme = HTTPBearer(auto_error=False)

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/register", response_model=TokenResponse, status_code=201)
@limiter.limit("10/minute")
async def register(
    request: Request,
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Register a new student account and return a JWT.

    - 201 Created on success
    - 409 Conflict if email already exists
    - 422 Unprocessable Entity on validation failure
    - 429 Too Many Requests if rate limit exceeded
    """
    return await auth_service.register_student(db, body)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate with email + password and return a JWT.

    - 200 OK on success
    - 401 Unauthorized on invalid credentials (generic — does not reveal
      whether the email exists)
    - 429 Too Many Requests if rate limit exceeded
    """
    return await auth_service.login(db, body)


@router.post("/logout", status_code=204)
async def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Invalidate the current JWT by adding its JTI to the denylist.

    - 204 No Content on success
    - 401 Unauthorized if no valid JWT is provided
    """
    # get_current_user already validated the token; decode again to get JTI.
    # This is safe because the token was already verified above.
    token = credentials.credentials  # type: ignore[union-attr]
    token_data = decode_access_token(token)
    await auth_service.logout(db, token_data)


@router.post("/reset-password/request", status_code=202)
async def reset_password_request(
    body: ResetPasswordRequestBody,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Request a password reset email.

    Always returns 202 Accepted regardless of whether the email exists,
    to prevent user enumeration.
    """
    await auth_service.request_password_reset(db, body.email)
    return {"detail": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password/confirm", status_code=200)
async def reset_password_confirm(
    body: ResetPasswordConfirmBody,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Apply a new password using a valid reset token.

    - 200 OK on success
    - 400 Bad Request if token is invalid, expired, or already used
    """
    await auth_service.confirm_password_reset(db, body.token, body.new_password)
    return {"detail": "Password updated successfully."}
