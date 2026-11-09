"""Lesson notes, student time zones and goals, credit reminders and amounts.

- users: timezone (IANA name, default UTC), learning_goal, goal_note
- lesson_notes: the tutor's notes, homework and new words for a lesson
- credit_grants: amount_cents (what the plan month cost, for the income
  figures) and expiry_reminder_sent_at (so the reminder goes out once)

Revision ID: 0004
Revises: 0003
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"))
    op.add_column("users", sa.Column("learning_goal", sa.String(30), nullable=True))
    op.add_column("users", sa.Column("goal_note", sa.String(500), nullable=True))

    op.create_table(
        "lesson_notes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "booking_id",
            UUID(as_uuid=True),
            sa.ForeignKey("bookings.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("homework", sa.Text(), nullable=True),
        sa.Column("vocabulary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.add_column("credit_grants", sa.Column("amount_cents", sa.Integer(), nullable=True))
    op.add_column(
        "credit_grants", sa.Column("expiry_reminder_sent_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("credit_grants", "expiry_reminder_sent_at")
    op.drop_column("credit_grants", "amount_cents")
    op.drop_table("lesson_notes")
    op.drop_column("users", "goal_note")
    op.drop_column("users", "learning_goal")
    op.drop_column("users", "timezone")
