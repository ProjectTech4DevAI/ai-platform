"""add fine tuning table

Revision ID: e3c74fab4356
Revises: 5a59c6c29a82
Create Date: 2025-08-04 22:03:54.552069

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql


revision = "e3c74fab4356"
down_revision = "5a59c6c29a82"
branch_labels = None
depends_on = None

finetuning_status_enum = postgresql.ENUM(
    "pending",
    "running",
    "completed",
    "failed",
    name="finetuningstatus",
    create_type=False,
)


def upgrade():
    finetuning_status_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "fine_tuning",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.Column("base_model", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("split_ratio", sa.Float(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["document.id"]),
        sa.Column(
            "training_file_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("testing_file_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("provider_job_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "status",
            finetuning_status_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "fine_tuned_model", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("error_message", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], ondelete="CASCADE"
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("inserted_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table("fine_tuning")
