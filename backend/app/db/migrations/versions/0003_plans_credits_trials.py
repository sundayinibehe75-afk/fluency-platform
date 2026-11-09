"""Monthly plans, lesson credits, free trials and new prices.

- price_configs: lessons_per_month, is_active, sort_order; single lesson now
  $10; old monthly/intensive packages hidden; plans for 2-5 lessons a week
- subscriptions: a student's Stripe-billed monthly plan
- credit_grants: lesson credits from a plan invoice or added by the tutor
- bookings: booking_type (single | plan | trial), credit_grant_id,
  late_cancellation

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

PLANS = [
    # product_key, label, price_cents, lessons_per_month, sort_order
    ("plan_2x", "2 lessons a week (8 per month)", 7600, 8, 2),
    ("plan_3x", "3 lessons a week (12 per month)", 10800, 12, 3),
    ("plan_4x", "4 lessons a week (16 per month)", 14000, 16, 4),
    ("plan_5x", "5 lessons a week (20 per month)", 17000, 20, 5),
]


def upgrade() -> None:
    # --- prices -----------------------------------------------------------
    op.add_column("price_configs", sa.Column("lessons_per_month", sa.Integer(), nullable=True))
    op.add_column("price_configs", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("price_configs", sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"))

    op.execute(
        "INSERT INTO price_configs (id, product_key, price_cents, currency, label, is_active, sort_order) "
        "VALUES (gen_random_uuid(), 'single_session', 1000, 'USD', 'Single lesson (60 min)', true, 1) "
        "ON CONFLICT (product_key) DO UPDATE SET price_cents = 1000, "
        "label = 'Single lesson (60 min)', sort_order = 1, is_active = true"
    )
    op.execute(
        "UPDATE price_configs SET is_active = false "
        "WHERE product_key IN ('monthly_package', 'intensive_package')"
    )
    for key, label, cents, lessons, order in PLANS:
        op.execute(
            sa.text(
                "INSERT INTO price_configs (id, product_key, price_cents, currency, label, "
                "lessons_per_month, is_active, sort_order) "
                "VALUES (gen_random_uuid(), :key, :cents, 'USD', :label, :lessons, true, :order) "
                "ON CONFLICT (product_key) DO NOTHING"
            ).bindparams(key=key, cents=cents, label=label, lessons=lessons, order=order)
        )

    # --- subscriptions ----------------------------------------------------
    op.create_table(
        "subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_key", sa.String(100), nullable=False),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=False, unique=True),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("subscriptions_student_idx", "subscriptions", ["student_id"])

    # --- credit grants ----------------------------------------------------
    op.create_table(
        "credit_grants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_id", UUID(as_uuid=True), sa.ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stripe_invoice_id", sa.String(255), nullable=True, unique=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("used >= 0 AND used <= total", name="credit_grants_used_range"),
    )
    op.create_index("credit_grants_student_idx", "credit_grants", ["student_id", "expires_at"])

    # --- bookings ---------------------------------------------------------
    op.add_column("bookings", sa.Column("booking_type", sa.String(20), nullable=False, server_default="single"))
    op.add_column(
        "bookings",
        sa.Column("credit_grant_id", UUID(as_uuid=True), sa.ForeignKey("credit_grants.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column("bookings", sa.Column("late_cancellation", sa.Boolean(), nullable=False, server_default=sa.text("false")))


def downgrade() -> None:
    op.drop_column("bookings", "late_cancellation")
    op.drop_column("bookings", "credit_grant_id")
    op.drop_column("bookings", "booking_type")
    op.drop_index("credit_grants_student_idx", table_name="credit_grants")
    op.drop_table("credit_grants")
    op.drop_index("subscriptions_student_idx", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.execute("DELETE FROM price_configs WHERE product_key LIKE 'plan\\_%x'")
    op.execute("UPDATE price_configs SET is_active = true, price_cents = 4500, label = 'Single Session' WHERE product_key = 'single_session'")
    op.drop_column("price_configs", "sort_order")
    op.drop_column("price_configs", "is_active")
    op.drop_column("price_configs", "lessons_per_month")
