"""Paystack auto-renewing plans.

A student who ticks "Renew automatically" gets a row in subscriptions with
provider = 'paystack'. Paystack gives us a reusable authorization code for
their card (not the card number); a background job charges it when the month
ends.

- provider: 'stripe' (existing rows) or 'paystack'
- paystack_authorization_code: token for charging the saved card
- card_label: e.g. "Visa ending 4081", shown to the student
- renewal_failures / last_charge_attempt_at: retry once a day, stop after 3
- reminder_sent_for: the period end we already sent the "renews soon" email for

Revision ID: 0006
Revises: 0005
"""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("provider", sa.String(20), nullable=False, server_default="stripe"),
    )
    op.add_column("subscriptions", sa.Column("paystack_authorization_code", sa.String(100), nullable=True))
    op.add_column("subscriptions", sa.Column("card_label", sa.String(60), nullable=True))
    op.add_column(
        "subscriptions",
        sa.Column("renewal_failures", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("subscriptions", sa.Column("last_charge_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("subscriptions", sa.Column("reminder_sent_for", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for column in (
        "reminder_sent_for",
        "last_charge_attempt_at",
        "renewal_failures",
        "card_label",
        "paystack_authorization_code",
        "provider",
    ):
        op.drop_column("subscriptions", column)
