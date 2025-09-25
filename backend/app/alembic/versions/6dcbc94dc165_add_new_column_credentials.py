"""add_new column credentials

Revision ID: 6dcbc94dc165
Revises: 6ed6ed401847
Create Date: 2025-09-25 15:02:41.730543

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "6dcbc94dc165"
down_revision = "6ed6ed401847"
branch_labels = None
depends_on = None


def upgrade():
    # Drop only deleted_at column from credential table, keep is_active for flexibility
    op.drop_column("credential", "deleted_at")


def downgrade():
    # Add back deleted_at column to credential table
    op.add_column("credential", sa.Column("deleted_at", sa.DateTime(), nullable=True))
