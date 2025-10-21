"""create_evaluation_run_table and batch_job_table

Revision ID: d5747495bd7c
Revises: e7c68e43ce6f
Create Date: 2025-10-14 12:42:15.464302

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "d5747495bd7c"
down_revision = "e7c68e43ce6f"
branch_labels = None
depends_on = None


def upgrade():
    # Create batch_job table first (as evaluation_run will reference it)
    op.create_table(
        "batch_job",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "provider",
            sa.String(),
            nullable=False,
            comment="LLM provider name (e.g., 'openai', 'anthropic')",
        ),
        sa.Column(
            "job_type",
            sa.String(),
            nullable=False,
            comment="Type of batch job (e.g., 'evaluation', 'classification', 'embedding')",
        ),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Complete batch configuration",
        ),
        sa.Column(
            "provider_batch_id",
            sa.String(),
            nullable=True,
            comment="Provider's batch job ID",
        ),
        sa.Column(
            "provider_file_id",
            sa.String(),
            nullable=True,
            comment="Provider's input file ID",
        ),
        sa.Column(
            "provider_output_file_id",
            sa.String(),
            nullable=True,
            comment="Provider's output file ID",
        ),
        sa.Column(
            "provider_status",
            sa.String(),
            nullable=True,
            comment="Provider-specific status (e.g., OpenAI: validating, in_progress, completed, failed)",
        ),
        sa.Column(
            "raw_output_url",
            sa.String(),
            nullable=True,
            comment="S3 URL of raw batch output file",
        ),
        sa.Column(
            "total_items",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Total number of items in the batch",
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
            comment="Error message if batch failed",
        ),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("inserted_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_batch_job_job_type"), "batch_job", ["job_type"], unique=False
    )
    op.create_index(
        op.f("ix_batch_job_organization_id"),
        "batch_job",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_batch_job_project_id"), "batch_job", ["project_id"], unique=False
    )

    # Create evaluation_run table with batch_job_id reference (no old batch columns)
    op.create_table(
        "evaluation_run",
        sa.Column("run_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("dataset_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("batch_job_id", sa.Integer(), nullable=True),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("s3_url", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("score", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("inserted_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["batch_job_id"], ["batch_job.id"]),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_evaluation_run_run_name"), "evaluation_run", ["run_name"], unique=False
    )


def downgrade():
    # Drop evaluation_run table first
    op.drop_index(op.f("ix_evaluation_run_run_name"), table_name="evaluation_run")
    op.drop_table("evaluation_run")

    # Drop batch_job table
    op.drop_index(op.f("ix_batch_job_project_id"), table_name="batch_job")
    op.drop_index(op.f("ix_batch_job_organization_id"), table_name="batch_job")
    op.drop_index(op.f("ix_batch_job_job_type"), table_name="batch_job")
    op.drop_table("batch_job")
