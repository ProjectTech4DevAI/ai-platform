"""add error message column in collections table

Revision ID: 5a59c6c29a82
Revises: e9dd35eff62c
Create Date: 2025-08-11 15:40:40.127161

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = '022'
down_revision = '021'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "collection",
        sa.Column("error_message", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )


def downgrade():
    op.drop_column("collection", "error_message")
