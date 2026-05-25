"""Seed script — creates an admin user and tutor profile for v1.

Run with: docker-compose exec api python seed.py
"""
import asyncio
import uuid

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.tutor import Tutor
from app.models.user import User
from app.models.price_config import PriceConfig


async def seed():
    async with AsyncSessionLocal() as db:
        # Check if admin already exists
        from sqlalchemy import select
        result = await db.execute(select(User).where(User.email == "admin@fluencytutoring.com"))
        existing = result.scalar_one_or_none()

        if existing:
            print("Admin already exists. Skipping seed.")
            return

        # Create admin user
        admin = User(
            id=uuid.uuid4(),
            email="admin@fluencytutoring.com",
            password_hash=hash_password("admin1234"),
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

        # Seed price configs
        prices = [
            PriceConfig(product_key="single_session", price_cents=4500, currency="USD", label="Single Session"),
            PriceConfig(product_key="monthly_package", price_cents=16000, currency="USD", label="Monthly Package (4 lessons)"),
            PriceConfig(product_key="intensive_package", price_cents=28000, currency="USD", label="Intensive Package (8 lessons)"),
        ]
        for p in prices:
            db.add(p)

        await db.commit()
        print("✅ Seed complete!")
        print(f"   Admin email: admin@fluencytutoring.com")
        print(f"   Admin password: admin1234")
        print(f"   Tutor ID: 00000000-0000-0000-0000-000000000001")
        print(f"   Price configs: single_session=$45, monthly=$160, intensive=$280")


if __name__ == "__main__":
    asyncio.run(seed())
