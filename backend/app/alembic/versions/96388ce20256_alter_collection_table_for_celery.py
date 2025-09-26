"""alter collection table for celery

Revision ID: 96388ce20256
Revises: 6ed6ed401847
Create Date: 2025-09-17 16:35:37.809812

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = "96388ce20256"
down_revision = "c6fb6d0b5897"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("collection_owner_id_fkey", "collection", type_="foreignkey")
    op.drop_column("collection", "owner_id")
    op.add_column(
        "collection",
        sa.Column("task_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )


def downgrade():
    op.drop_column("collection", "task_id")
    op.add_column(
        "collection",
        sa.Column("owner_id", sa.INTEGER(), autoincrement=False, nullable=False),
    )
    op.create_foreign_key(
        "collection_owner_id_fkey",
        "collection",
        "user",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )
