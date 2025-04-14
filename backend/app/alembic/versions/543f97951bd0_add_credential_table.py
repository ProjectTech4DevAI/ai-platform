"""add credetial table

Revision ID: 543f97951bd0
Revises: 8d7a05fd0ad4
Create Date: 2025-04-14 23:50:51.118373

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = "543f97951bd0"
down_revision = "8d7a05fd0ad4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "credential",
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("credential", sa.JSON(), nullable=True),
        sa.Column("inserted_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("credential")
