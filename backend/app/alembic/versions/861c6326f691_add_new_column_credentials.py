"""drop column deleted_at from credentials

Revision ID: 861c6326f691
Revises: c6fb6d0b5897
Create Date: 2025-10-06 12:35:25.354540

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "861c6326f691"
down_revision = "c6fb6d0b5897"
branch_labels = None
depends_on = None


def upgrade():
    # Drop only deleted_at column from credential table, keep is_active for flexibility
    op.drop_column("credential", "deleted_at")

    # Add unique constraint on organization_id, project_id, provider
    op.create_unique_constraint(
        "uq_credential_org_project_provider",
        "credential",
        ["organization_id", "project_id", "provider"],
    )


def downgrade():
    # Add back deleted_at column to credential table
    op.add_column("credential", sa.Column("deleted_at", sa.DateTime(), nullable=True))

    # Drop the unique constraint
    op.drop_constraint(
        "uq_credential_org_project_provider", "credential", type_="unique"
    )
