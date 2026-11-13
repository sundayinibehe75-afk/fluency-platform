"""Paystack payments: exchange rate setting and payment references.

- app_settings: small key/value table for settings the admin changes in the
  dashboard (first one: ngn_per_usd, the naira rate used at checkout)
- bookings.payment_provider / payment_reference: which provider took the
  payment and its transaction reference (used for verification and refunds)
- credit_grants.payment_reference: the transaction that paid for a lesson
  package, unique so a package is never granted twice

Revision ID: 0005
Revises: 0004
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(50), primary_key=True),
        sa.Column("value", sa.String(200), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.add_column("bookings", sa.Column("payment_provider", sa.String(20), nullable=True))
    op.add_column("bookings", sa.Column("payment_reference", sa.String(100), nullable=True))
    op.create_unique_constraint("bookings_payment_reference_key", "bookings", ["payment_reference"])
    op.add_column("credit_grants", sa.Column("payment_reference", sa.String(100), nullable=True))
    op.create_unique_constraint(
        "credit_grants_payment_reference_key", "credit_grants", ["payment_reference"]
    )


def downgrade() -> None:
    op.drop_constraint("credit_grants_payment_reference_key", "credit_grants", type_="unique")
    op.drop_column("credit_grants", "payment_reference")
    op.drop_constraint("bookings_payment_reference_key", "bookings", type_="unique")
    op.drop_column("bookings", "payment_reference")
    op.drop_column("bookings", "payment_provider")
    op.drop_table("app_settings")
