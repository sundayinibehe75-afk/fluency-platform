"""Health check endpoint.

GET /health — attempts a lightweight DB query (SELECT 1).
Returns:
  - {"status": "ok"}       HTTP 200  when the DB is reachable
  - {"status": "degraded"} HTTP 503  when the DB is unreachable
"""
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Return service health, including a lightweight DB connectivity check."""
    try:
        await db.execute(text("SELECT 1"))
        return JSONResponse(status_code=200, content={"status": "ok"})
    except Exception as exc:  # noqa: BLE001
        logger.error("Health check DB query failed", exc_info=exc)
        return JSONResponse(status_code=503, content={"status": "degraded"})
