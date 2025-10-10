"""delete processing and failed columns from collection table

Revision ID: 7ab577d3af26
Revises: c6fb6d0b5897
Create Date: 2025-10-06 13:59:28.561706

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = "7ab577d3af26"
down_revision = "c6fb6d0b5897"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        DELETE FROM collection
        WHERE status IN ('processing', 'failed')
        """
    )
    op.execute(
        """
        DELETE FROM collection
        WHERE llm_service_id IS NULL
        """
    )


def downgrade():
    pass
