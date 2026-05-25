"""FastAPI application factory.

Responsibilities:
- Configure structured JSON logging
- Create the FastAPI app instance
- Register CORS middleware
- Register security-header middleware (HSTS, X-Content-Type-Options,
  X-Frame-Options, Content-Security-Policy)
- Register a global exception handler that logs unhandled exceptions with
  a full stack trace and returns a generic 500 JSON response
- Mount all API routers under the /api prefix
"""
import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import settings
from app.core.logging import configure_logging

# Routers (stubs for now; each will be fully implemented in its own task)
from app.routers import (
    auth,
    availability,
    bookings,
    health,
    messages,
    payments,
    reviews,
    tutors,
    users,
)

# ---------------------------------------------------------------------------
# Logging — must be configured before the app is created so that startup
# events and middleware are already covered.
# ---------------------------------------------------------------------------
configure_logging(level="DEBUG" if settings.environment == "development" else "INFO")

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Security-header middleware
# ---------------------------------------------------------------------------
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach security headers to every response.

    Headers applied:
    - Strict-Transport-Security (HSTS)
    - X-Content-Type-Options
    - X-Frame-Options
    - Content-Security-Policy (restrictive default)
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        response.headers["Strict-Transport-Security"] = (
            "max-age=63072000; includeSubDomains; preload"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        return response


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Fluency Platform API",
        version="1.0.0",
        # Disable the default /docs and /redoc in production
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url="/redoc" if settings.environment != "production" else None,
    )

    # -----------------------------------------------------------------------
    # Rate limiting — attach the limiter from the auth router so that
    # slowapi can find it via app.state.limiter.
    # -----------------------------------------------------------------------
    app.state.limiter = auth.limiter

    async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={
                "error": "RATE_LIMITED",
                "detail": "Too many requests. Please try again later.",
            },
        )

    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
    app.add_middleware(SlowAPIMiddleware)

    # -----------------------------------------------------------------------
    # CORS middleware
    # -----------------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -----------------------------------------------------------------------
    # Security headers middleware
    # -----------------------------------------------------------------------
    app.add_middleware(SecurityHeadersMiddleware)

    # -----------------------------------------------------------------------
    # Global exception handler — catches any unhandled exception, logs it
    # with a full stack trace, and returns a generic 500 response so that
    # internal details are never leaked to the client.
    # -----------------------------------------------------------------------
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error(
            "Unhandled exception",
            exc_info=exc,
            extra={
                "method": request.method,
                "url": str(request.url),
                "traceback": traceback.format_exc(),
            },
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "detail": "An unexpected error occurred. Please try again later.",
            },
        )

    # -----------------------------------------------------------------------
    # Routers — all mounted under /api
    # -----------------------------------------------------------------------
    API_PREFIX = "/api"

    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(users.router, prefix=API_PREFIX)
    app.include_router(tutors.router, prefix=API_PREFIX)
    app.include_router(availability.router, prefix=API_PREFIX)
    app.include_router(bookings.router, prefix=API_PREFIX)
    app.include_router(payments.router, prefix=API_PREFIX)
    app.include_router(messages.router, prefix=API_PREFIX)
    app.include_router(reviews.router, prefix=API_PREFIX)

    logger.info(
        "Fluency Platform API started",
        extra={"environment": settings.environment},
    )

    return app


app = create_app()
