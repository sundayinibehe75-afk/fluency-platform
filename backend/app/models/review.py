"""Review ORM model."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
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
    # CHECK (rating BETWEEN 1 AND 5)
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # Max 1000 chars enforced at the application layer
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_hidden: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    booking: Mapped["Booking"] = relationship(  # noqa: F821
        "Booking", back_populates="review"
    )
    student: Mapped["User"] = relationship(  # noqa: F821
        "User", foreign_keys=[student_id], back_populates="reviews_as_student"
    )
    tutor: Mapped["Tutor"] = relationship(  # noqa: F821
        "Tutor", foreign_keys=[tutor_id], back_populates="reviews"
    )

    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="reviews_rating_check"),
        Index("reviews_tutor_idx", "tutor_id", "is_hidden", "submitted_at"),
    )

    def __repr__(self) -> str:
        return f"<Review id={self.id} rating={self.rating} is_hidden={self.is_hidden}>"
