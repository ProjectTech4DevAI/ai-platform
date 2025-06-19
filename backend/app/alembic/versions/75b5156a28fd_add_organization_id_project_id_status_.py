"""Add organization_id, project_id, status, and updated_at to Collection

Revision ID: 75b5156a28fd
Revises: 8757b005d681
Create Date: 2025-06-19 15:38:02.609786

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = "75b5156a28fd"
down_revision = "8757b005d681"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "collection", sa.Column("organization_id", sa.Integer(), nullable=False)
    )
    op.add_column("collection", sa.Column("project_id", sa.Integer(), nullable=True))
    op.add_column(
        "collection",
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.add_column("collection", sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.alter_column(
        "collection", "llm_service_id", existing_type=sa.VARCHAR(), nullable=True
    )
    op.alter_column(
        "collection", "llm_service_name", existing_type=sa.VARCHAR(), nullable=True
    )
    op.create_foreign_key(
        None, "collection", "project", ["project_id"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        None,
        "collection",
        "organization",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade():
    op.drop_constraint(None, "collection", type_="foreignkey")
    op.drop_constraint(None, "collection", type_="foreignkey")
    op.alter_column(
        "collection", "llm_service_name", existing_type=sa.VARCHAR(), nullable=False
    )
    op.alter_column(
        "collection", "llm_service_id", existing_type=sa.VARCHAR(), nullable=False
    )
    op.drop_column("collection", "updated_at")
    op.drop_column("collection", "status")
    op.drop_column("collection", "project_id")
    op.drop_column("collection", "organization_id")
