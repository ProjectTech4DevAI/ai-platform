"""drop column deleted_at from credentials

Revision ID: 27c271ab6dd0
Revises: 93d484f5798e
Create Date: 2025-10-15 11:10:02.554097

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "27c271ab6dd0"
down_revision = "93d484f5798e"
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
