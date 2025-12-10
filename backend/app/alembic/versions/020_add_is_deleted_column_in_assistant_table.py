"""Add is_deleted column in assistant table

Revision ID: 020
Revises: 019
Create Date: 2025-07-21 12:40:03.791321

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "openai_assistant",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "openai_assistant", sa.Column("deleted_at", sa.DateTime(), nullable=True)
    )


def downgrade():
    op.drop_column("openai_assistant", "deleted_at")
    op.drop_column("openai_assistant", "is_deleted")
