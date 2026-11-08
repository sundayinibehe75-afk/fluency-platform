"""Allow a slot to be re-booked after a cancellation.

The initial schema made bookings.slot_id UNIQUE, so once a booking existed for
a slot — even a cancelled or expired one — nobody could book that slot again.
This replaces it with a partial unique index: one *active* booking
(pending_payment or confirmed) per slot.

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("bookings_slot_id_key", "bookings", type_="unique")
    op.create_index(
        "bookings_active_slot_uidx",
        "bookings",
        ["slot_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending_payment', 'confirmed')"),
    )


def downgrade() -> None:
    op.drop_index("bookings_active_slot_uidx", table_name="bookings")
    op.create_unique_constraint("bookings_slot_id_key", "bookings", ["slot_id"])
