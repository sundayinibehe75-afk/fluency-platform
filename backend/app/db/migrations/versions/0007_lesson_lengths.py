"""30-minute lessons.

- price_configs.lesson_minutes: 60 for existing prices; new 30-minute prices:
  single_session_30 ($6) and a 30-minute version of every plan, at the same
  per-lesson discount as the 60-minute plans
- credit_grants.lesson_minutes: a plan's lessons can only book lessons of
  that length (existing grants are 60-minute)

Revision ID: 0007
Revises: 0006
"""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

NEW_PRICES = [
    # product_key, label, price_cents, lessons_per_month, sort_order
    ("single_session_30", "Single lesson (30 min)", 600, None, 11),
    ("plan_2x_30", "2 lessons a week, 30 min (8 per month)", 4600, 8, 12),
    ("plan_3x_30", "3 lessons a week, 30 min (12 per month)", 6500, 12, 13),
    ("plan_4x_30", "4 lessons a week, 30 min (16 per month)", 8400, 16, 14),
    ("plan_5x_30", "5 lessons a week, 30 min (20 per month)", 10200, 20, 15),
]


def upgrade() -> None:
    op.add_column(
        "price_configs", sa.Column("lesson_minutes", sa.Integer(), nullable=False, server_default="60")
    )
    op.add_column(
        "credit_grants", sa.Column("lesson_minutes", sa.Integer(), nullable=False, server_default="60")
    )
    for key, label, cents, lessons, order in NEW_PRICES:
        op.execute(
            sa.text(
                "INSERT INTO price_configs (id, product_key, price_cents, currency, label, "
                "lessons_per_month, is_active, sort_order, lesson_minutes) "
                "VALUES (gen_random_uuid(), :key, :cents, 'USD', :label, :lessons, true, :order, 30) "
                "ON CONFLICT (product_key) DO NOTHING"
            ).bindparams(key=key, cents=cents, label=label, lessons=lessons, order=order)
        )


def downgrade() -> None:
    op.execute("DELETE FROM price_configs WHERE lesson_minutes = 30 AND product_key NOT IN "
               "(SELECT DISTINCT product_key FROM subscriptions)")
    op.drop_column("credit_grants", "lesson_minutes")
    op.drop_column("price_configs", "lesson_minutes")
