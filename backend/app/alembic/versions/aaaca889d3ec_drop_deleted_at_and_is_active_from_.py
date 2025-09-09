"""drop_deleted_at_from_credential_table

Revision ID: 7a0e8ab42c69
Revises: 40307ab77e9f
Create Date: 2025-09-01 21:52:33.293932

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "7a0e8ab42c69"
down_revision = "40307ab77e9f"
branch_labels = None
depends_on = None


def upgrade():
    # Drop only deleted_at column from credential table, keep is_active for flexibility
    op.drop_column("credential", "deleted_at")


def downgrade():
    # Add back deleted_at column to credential table
    op.add_column("credential", sa.Column("deleted_at", sa.DateTime(), nullable=True))
