"""AvailabilitySlot ORM model."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AvailabilitySlot(Base):
    __tablename__ = "availability_slots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tutor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tutors.id", ondelete="CASCADE"),
        nullable=False,
    )
    start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    end_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    # available | booked
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    # Links slots from the same recurring pattern
    recurrence_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    tutor: Mapped["Tutor"] = relationship(  # noqa: F821
        "Tutor", back_populates="availability_slots"
    )
    booking: Mapped["Booking | None"] = relationship(  # noqa: F821
        "Booking", back_populates="slot", uselist=False
    )

    __table_args__ = (
        Index("slots_tutor_start_idx", "tutor_id", "start_at"),
        Index("slots_status_idx", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<AvailabilitySlot id={self.id} tutor_id={self.tutor_id} "
            f"start_at={self.start_at} status={self.status}>"
        )
