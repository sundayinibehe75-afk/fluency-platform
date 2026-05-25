"""User ORM model."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # student | tutor | admin
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    # A0–C2, nullable
    cefr_level: Mapped[str | None] = mapped_column(String(5), nullable=True)
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
    tutor_profile: Mapped["Tutor"] = relationship(  # noqa: F821
        "Tutor", back_populates="user", uselist=False
    )
    bookings_as_student: Mapped[list["Booking"]] = relationship(  # noqa: F821
        "Booking", foreign_keys="Booking.student_id", back_populates="student"
    )
    sent_messages: Mapped[list["Message"]] = relationship(  # noqa: F821
        "Message", foreign_keys="Message.sender_id", back_populates="sender"
    )
    received_messages: Mapped[list["Message"]] = relationship(  # noqa: F821
        "Message", foreign_keys="Message.recipient_id", back_populates="recipient"
    )
    reviews_as_student: Mapped[list["Review"]] = relationship(  # noqa: F821
        "Review", foreign_keys="Review.student_id", back_populates="student"
    )
    password_reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(  # noqa: F821
        "PasswordResetToken", back_populates="user"
    )

    __table_args__ = (
        Index("users_email_idx", "email", unique=True),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"
