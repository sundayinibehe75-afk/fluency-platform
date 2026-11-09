import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LessonNote(Base):
    """What the tutor writes after a lesson: summary, homework, new words.

    vocabulary holds one entry per line, e.g. "der Bahnhof - train station".
    """

    __tablename__ = "lesson_notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    homework: Mapped[str | None] = mapped_column(Text, nullable=True)
    vocabulary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
