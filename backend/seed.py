"""Seed script — creates an admin user and tutor profile for v1.

Run with: docker-compose exec api python seed.py
"""
import asyncio
import os
import sys
import uuid

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.tutor import Tutor
from app.models.user import User
from app.models.price_config import PriceConfig


ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "").strip().lower()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")


async def seed():
    if not ADMIN_EMAIL or len(ADMIN_PASSWORD) < 12:
        sys.exit(
            "Set ADMIN_EMAIL and ADMIN_PASSWORD (12+ characters), e.g.\n"
            "  docker compose exec -e ADMIN_EMAIL=you@example.com "
            "-e ADMIN_PASSWORD='...' api python seed.py"
        )
    async with AsyncSessionLocal() as db:
        # Check if admin already exists
        from sqlalchemy import select
        result = await db.execute(select(User).where(User.role == "admin"))
        existing = result.scalar_one_or_none()

        if existing:
            print("Admin already exists. Skipping seed.")
            return

        # Create admin user
        admin = User(
            id=uuid.uuid4(),
            email=ADMIN_EMAIL,
            password_hash=hash_password(ADMIN_PASSWORD),
            first_name="Admin",
            last_name="Tutor",
            role="admin",
        )
        db.add(admin)
        await db.flush()

        # Create tutor profile linked to admin
        tutor = Tutor(
            id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            user_id=admin.id,
            display_name="Sunday - German Tutor",
            bio="Professional German tutor with years of experience helping students reach their language goals. I specialize in making German approachable, practical, and enjoyable.",
            spoken_languages=["English", "German"],
            specialisms=["Beginner German", "Business German", "Exam Preparation", "Conversation Practice"],
            cefr_levels_taught=["A1", "A2", "B1", "B2", "C1", "C2"],
            years_experience=5,
        )
        db.add(tutor)

        # Seed prices that don't exist yet (migration 0003 also adds the plans)
        wanted = [
            ("single_session", 1000, "Single lesson (60 min)", None, 1),
            ("plan_2x", 7600, "2 lessons a week (8 per month)", 8, 2),
            ("plan_3x", 10800, "3 lessons a week (12 per month)", 12, 3),
            ("plan_4x", 14000, "4 lessons a week (16 per month)", 16, 4),
            ("plan_5x", 17000, "5 lessons a week (20 per month)", 20, 5),
        ]
        existing_keys = set((await db.execute(select(PriceConfig.product_key))).scalars())
        for key, cents, label, lessons, order in wanted:
            if key not in existing_keys:
                db.add(PriceConfig(
                    product_key=key, price_cents=cents, currency="USD", label=label,
                    lessons_per_month=lessons, sort_order=order,
                ))

        await db.commit()
        print("✅ Seed complete!")
        print(f"   Admin email: {ADMIN_EMAIL}")
        print(f"   Tutor ID: 00000000-0000-0000-0000-000000000001")
        print("   Prices: single lesson $10; plans 2x/3x/4x/5x a week = $76/$108/$140/$170")


if __name__ == "__main__":
    asyncio.run(seed())
