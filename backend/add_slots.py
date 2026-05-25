"""Add sample availability slots for the next 7 days.

Run with: docker-compose exec api python add_slots.py
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from app.db.session import AsyncSessionLocal
from app.models.availability_slot import AvailabilitySlot


TUTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def add_slots():
    async with AsyncSessionLocal() as db:
        now = datetime.now(tz=timezone.utc)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        slots_created = 0
        
        # Create slots for the next 7 days, 3 slots per day (9am, 12pm, 3pm UTC)
        for day_offset in range(1, 8):
            day = today + timedelta(days=day_offset)
            
            for hour in [9, 12, 15]:
                start = day.replace(hour=hour)
                end = start + timedelta(minutes=60)
                
                slot = AvailabilitySlot(
                    id=uuid.uuid4(),
                    tutor_id=TUTOR_ID,
                    start_at=start,
                    end_at=end,
                    duration_minutes=60,
                    status="available",
                )
                db.add(slot)
                slots_created += 1
        
        await db.commit()
        print(f"✅ Created {slots_created} availability slots for the next 7 days!")
        print(f"   Times: 9:00 AM, 12:00 PM, 3:00 PM (UTC)")
        print(f"   Duration: 60 minutes each")
        print(f"   Tutor ID: {TUTOR_ID}")


if __name__ == "__main__":
    asyncio.run(add_slots())
