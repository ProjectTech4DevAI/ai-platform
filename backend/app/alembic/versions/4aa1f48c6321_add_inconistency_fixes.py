"""add anything

Revision ID: 4aa1f48c6321
Revises: 3389c67fdcb4
Create Date: 2025-07-03 16:46:13.642386

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "4aa1f48c6321"
down_revision = "3389c67fdcb4"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "collection", "project_id", existing_type=sa.INTEGER(), nullable=False
    )
    op.alter_column(
        "credential",
        "inserted_at",
        existing_type=postgresql.TIMESTAMP(),
        nullable=False,
    )
    op.alter_column(
        "credential", "updated_at", existing_type=postgresql.TIMESTAMP(), nullable=False
    )
    op.create_index(
        op.f("ix_openai_assistant_assistant_id"),
        "openai_assistant",
        ["assistant_id"],
        unique=True,
    )
    op.drop_constraint("project_organization_id_fkey", "project", type_="foreignkey")
    op.create_foreign_key(
        None, "project", "organization", ["organization_id"], ["id"], ondelete="CASCADE"
    )


def downgrade():
    op.drop_constraint(None, "project", type_="foreignkey")
    op.create_foreign_key(
        "project_organization_id_fkey",
        "project",
        "organization",
        ["organization_id"],
        ["id"],
    )
    op.drop_index(
        op.f("ix_openai_assistant_assistant_id"), table_name="openai_assistant"
    )
    op.drop_constraint(None, "credential", type_="foreignkey")
    op.create_foreign_key(
        "credential_project_id_fkey",
        "credential",
        "project",
        ["project_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column(
        "credential", "updated_at", existing_type=postgresql.TIMESTAMP(), nullable=True
    )
    op.alter_column(
        "credential", "inserted_at", existing_type=postgresql.TIMESTAMP(), nullable=True
    )
    op.alter_column(
        "credential", "project_id", existing_type=sa.INTEGER(), nullable=True
    )
    op.alter_column(
        "collection", "project_id", existing_type=sa.INTEGER(), nullable=True
    )
