"""Booking ORM model."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    tutor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tutors.id", ondelete="RESTRICT"),
        nullable=False,
    )
    slot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("availability_slots.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    # pending_payment | confirmed | cancelled | completed | refunded
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default="USD"
    )
    stripe_session_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True
    )
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    video_room_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 15-minute hold window
    reserved_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    student: Mapped["User"] = relationship(  # noqa: F821
        "User", foreign_keys=[student_id], back_populates="bookings_as_student"
    )
    tutor: Mapped["Tutor"] = relationship(  # noqa: F821
        "Tutor", foreign_keys=[tutor_id], back_populates="bookings"
    )
    slot: Mapped["AvailabilitySlot"] = relationship(  # noqa: F821
        "AvailabilitySlot", back_populates="booking"
    )
    payments: Mapped[list["Payment"]] = relationship(  # noqa: F821
        "Payment", back_populates="booking"
    )
    review: Mapped["Review | None"] = relationship(  # noqa: F821
        "Review", back_populates="booking", uselist=False
    )

    __table_args__ = (
        Index("bookings_student_idx", "student_id"),
        Index("bookings_tutor_idx", "tutor_id"),
        Index("bookings_status_idx", "status"),
    )

    def __repr__(self) -> str:
        return f"<Booking id={self.id} status={self.status}>"
