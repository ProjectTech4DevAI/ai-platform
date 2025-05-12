"""Added provider column to the credential table

Revision ID: 904ed70e7dab
Revises: 543f97951bd0
Create Date: 2025-05-10 11:13:17.868238

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


revision = "904ed70e7dab"
down_revision = "f23675767ed2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "credential",
        sa.Column("provider", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    )
    op.create_index(
        op.f("ix_credential_provider"), "credential", ["provider"], unique=False
    )
    op.drop_constraint(
        "credential_organization_id_fkey", "credential", type_="foreignkey"
    )
    op.create_foreign_key(
        "credential_organization_id_fkey",
        "credential",
        "organization",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("project_organization_id_fkey", "project", type_="foreignkey")
    op.create_foreign_key(None, "project", "organization", ["organization_id"], ["id"])


def downgrade():
    op.drop_constraint(None, "project", type_="foreignkey")
    op.create_foreign_key(
        "project_organization_id_fkey",
        "project",
        "organization",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint(
        "credential_organization_id_fkey", "credential", type_="foreignkey"
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
