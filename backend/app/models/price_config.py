"""PriceConfig ORM model."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PriceConfig(Base):
    __tablename__ = "price_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default="USD"
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    # Monthly plans: number of lessons granted each month (None = single lesson)
    lessons_per_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Hidden products stay in the table for old bookings but aren't offered
    lesson_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60, server_default="60")
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<PriceConfig id={self.id} product_key={self.product_key} price_cents={self.price_cents}>"
