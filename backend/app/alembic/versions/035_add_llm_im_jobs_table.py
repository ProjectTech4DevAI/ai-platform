"""Add LLM in jobs table

Revision ID: 219033c644de
Revises: e7c68e43ce6f
Create Date: 2025-10-17 15:38:33.565674

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE jobtype ADD VALUE IF NOT EXISTS 'LLM_API'")


def downgrade():
    # Enum value removal requires manual intervention if 'LLM_API' is in use.
    # If rollback is necessary, run SQL manually to recreate the enum without 'LLM_API'.
    pass
