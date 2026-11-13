import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Subscription(Base):
    """A student's monthly plan, renewed automatically.

    provider 'stripe': billed by Stripe. provider 'paystack': we charge the
    student's saved card (paystack_authorization_code) when the month ends;
    stripe_subscription_id then holds our own id ("paystack:<uuid>").

    status mirrors Stripe: active, past_due, canceled, incomplete, ...
    cancel_at_period_end is True once the student has cancelled: the plan
    then stops at current_period_end and is not renewed.
    """

    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    product_key: Mapped[str] = mapped_column(String(100), nullable=False)
    stripe_subscription_id: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False, server_default="stripe")
    paystack_authorization_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    card_label: Mapped[str | None] = mapped_column(String(60), nullable=True)
    renewal_failures: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_charge_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reminder_sent_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __mapper_args__ = {"eager_defaults": True}

    __table_args__ = (Index("subscriptions_student_idx", "student_id"),)
