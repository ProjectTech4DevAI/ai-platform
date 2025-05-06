"""add threads table

Revision ID: 9baa692f9a5d
Revises: 543f97951bd0
Create Date: 2025-05-05 23:25:37.195415

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = "9baa692f9a5d"
down_revision = "543f97951bd0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "threadresponse",
        sa.Column("thread_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("message", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("question", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("thread_id"),
    )


def downgrade():
    op.drop_table("threadresponse")
