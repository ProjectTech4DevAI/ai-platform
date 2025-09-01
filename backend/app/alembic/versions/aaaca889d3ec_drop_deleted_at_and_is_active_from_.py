"""drop_deleted_at_from_credential_table

Revision ID: aaaca889d3ec
Revises: 8725df286943
Create Date: 2025-08-31 16:15:15.078191

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = "aaaca889d3ec"
down_revision = "8725df286943"
branch_labels = None
depends_on = None


def upgrade():
    # Drop only deleted_at column from credential table, keep is_active for flexibility
    op.drop_column("credential", "deleted_at")


def downgrade():
    # Add back deleted_at column to credential table
    op.add_column("credential", sa.Column("deleted_at", sa.DateTime(), nullable=True))
