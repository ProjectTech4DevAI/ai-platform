"""Added provider column to the credential table

Revision ID: 012
Revises: 011
Create Date: 2025-05-10 11:13:17.868238

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to credential table
    op.add_column(
        "credential",
        sa.Column("provider", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    )
    op.add_column("credential", sa.Column("project_id", sa.Integer(), nullable=True))

    # Create indexes and constraints
    op.create_index(
        op.f("ix_credential_provider"), "credential", ["provider"], unique=False
    )

    # Drop existing foreign keys
    op.drop_constraint(
        "credential_organization_id_fkey", "credential", type_="foreignkey"
    )
    op.drop_constraint("project_organization_id_fkey", "project", type_="foreignkey")

    # Create all foreign keys together
    op.create_foreign_key(
        "credential_organization_id_fkey",
        "credential",
        "organization",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        None,
        "project",
        "organization",
        ["organization_id"],
        ["id"],
    )
    op.create_foreign_key(
        "credential_project_id_fkey",
        "credential",
        "project",
        ["project_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    # Drop project_id foreign key and column
    op.drop_constraint("credential_project_id_fkey", "credential", type_="foreignkey")
    op.drop_column("credential", "project_id")

    # Drop existing foreign keys
    op.drop_constraint(None, "project", type_="foreignkey")
    op.drop_constraint(
        "credential_organization_id_fkey", "credential", type_="foreignkey"
    )

    # Create all foreign keys together
    op.create_foreign_key(
        "project_organization_id_fkey",
        "project",
        "organization",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "credential_organization_id_fkey",
        "credential",
        "organization",
        ["organization_id"],
        ["id"],
    )

    op.drop_index(op.f("ix_credential_provider"), table_name="credential")
    op.drop_column("credential", "provider")
