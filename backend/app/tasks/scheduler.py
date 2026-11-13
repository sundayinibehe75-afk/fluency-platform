"""Background jobs that run inside the API process.

- every minute:   release unpaid bookings whose 15-minute reservation ended
- every 5 min:    mark confirmed lessons that have finished as 'completed'
- every 2 min:    email people about messages unread for 5 minutes
- every hour:     send 24-hour lesson reminder emails, and warn students whose
                  unbooked plan lessons expire within 5 days; renew Paystack
                  plans that are due (with reminder and failure emails)

Each job uses its own database session and commits its own work, so one
failing job never affects the others or the web requests.
"""
import asyncio
import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

Job = Callable[[AsyncSession], Awaitable[int]]


async def run_job(name: str, job: Job) -> None:
    """Run one job in a fresh session; log and swallow any error."""
    try:
        async with AsyncSessionLocal() as session:
            count = await job(session)
            await session.commit()
            if count:
                logger.info("Background job finished", extra={"job": name, "count": count})
    except Exception:
        logger.exception("Background job failed", extra={"job": name})


async def _every(seconds: int, name: str, job: Job) -> None:
    while True:
        await run_job(name, job)
        await asyncio.sleep(seconds)


def start_background_jobs() -> list[asyncio.Task]:
    """Start all periodic jobs and return their tasks (cancelled on shutdown)."""
    from app.services.booking_service import (
        complete_finished_bookings,
        expire_pending_bookings,
    )
    from app.services.credit_service import send_expiry_reminders
    from app.services.messaging_service import notify_unread_messages
    from app.services.paystack_service import renew_due_plans
    from app.tasks.reminder_task import send_lesson_reminders

    return [
        asyncio.create_task(_every(60, "expire_pending_bookings", expire_pending_bookings)),
        asyncio.create_task(_every(300, "complete_finished_bookings", complete_finished_bookings)),
        asyncio.create_task(_every(120, "notify_unread_messages", notify_unread_messages)),
        asyncio.create_task(_every(3600, "send_lesson_reminders", send_lesson_reminders)),
        asyncio.create_task(_every(3600, "send_expiry_reminders", send_expiry_reminders)),
        asyncio.create_task(_every(3600, "renew_due_plans", renew_due_plans)),
    ]
