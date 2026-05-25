"""Tutor ORM model."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Tutor(Base):
    __tablename__ = "tutors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # JSONB arrays, e.g. ["English", "Spanish"]
    spoken_languages: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    specialisms: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    cefr_levels_taught: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    years_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_rating: Mapped[float] = mapped_column(
        Numeric(3, 1), nullable=False, server_default="0.0"
    )
    review_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    user: Mapped["User"] = relationship(  # noqa: F821
        "User", back_populates="tutor_profile"
    )
    availability_slots: Mapped[list["AvailabilitySlot"]] = relationship(  # noqa: F821
        "AvailabilitySlot", back_populates="tutor"
    )
    bookings: Mapped[list["Booking"]] = relationship(  # noqa: F821
        "Booking", foreign_keys="Booking.tutor_id", back_populates="tutor"
    )
    reviews: Mapped[list["Review"]] = relationship(  # noqa: F821
        "Review", foreign_keys="Review.tutor_id", back_populates="tutor"
    )

    def __repr__(self) -> str:
        return f"<Tutor id={self.id} display_name={self.display_name}>"
