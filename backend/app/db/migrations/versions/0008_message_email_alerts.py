"""Email alerts for unread messages.

messages.email_notified: True once the recipient was emailed about this
message (or it was read first). Existing messages are marked as notified so
nobody gets emailed about old conversations.

Revision ID: 0008
Revises: 0007
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("email_notified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.execute("UPDATE messages SET email_notified = true")


def downgrade() -> None:
    op.drop_column("messages", "email_notified")
