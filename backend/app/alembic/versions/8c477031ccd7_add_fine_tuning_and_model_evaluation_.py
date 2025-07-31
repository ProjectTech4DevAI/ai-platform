"""add fine tuning and model evaluation table

Revision ID: 8c477031ccd7
Revises: e9dd35eff62c
Create Date: 2025-07-30 22:58:22.671782

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

# revision identifiers, used by Alembic.
revision = "8c477031ccd7"
down_revision = "e9dd35eff62c"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "fine_tuning",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("base_model", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("split_ratio", type_=sa.Float(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["document.id"],
        ),
        sa.Column(
            "training_file_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("testing_file_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("openai_job_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "fine_tuned_model", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("error_message", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], ondelete="CASCADE"
        ),
        sa.Column(
            "is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")
        ),
        sa.Column("inserted_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("fine_tuning")
