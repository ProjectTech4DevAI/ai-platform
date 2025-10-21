"""Add batch_job table and refactor evaluation_run

Revision ID: add_batch_job
Revises: 93d484f5798e
Create Date: 2025-10-21 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "add_batch_job"
down_revision = ("93d484f5798e", "d5747495bd7c", "27c271ab6dd0")
branch_labels = None
depends_on = None


def upgrade():
    # Create batch_job table
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
            default=0,
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

    # Add batch_job_id to evaluation_run
    op.add_column(
        "evaluation_run", sa.Column("batch_job_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_evaluation_run_batch_job_id",
        "evaluation_run",
        "batch_job",
        ["batch_job_id"],
        ["id"],
    )

    # Drop batch-related columns from evaluation_run
    op.drop_column("evaluation_run", "batch_status")
    op.drop_column("evaluation_run", "batch_id")
    op.drop_column("evaluation_run", "batch_file_id")
    op.drop_column("evaluation_run", "batch_output_file_id")


def downgrade():
    # Add back batch-related columns to evaluation_run
    op.add_column(
        "evaluation_run",
        sa.Column("batch_output_file_id", sa.String(), nullable=True),
    )
    op.add_column(
        "evaluation_run", sa.Column("batch_file_id", sa.String(), nullable=True)
    )
    op.add_column("evaluation_run", sa.Column("batch_id", sa.String(), nullable=True))
    op.add_column(
        "evaluation_run", sa.Column("batch_status", sa.String(), nullable=True)
    )

    # Drop batch_job_id from evaluation_run
    op.drop_constraint(
        "fk_evaluation_run_batch_job_id", "evaluation_run", type_="foreignkey"
    )
    op.drop_column("evaluation_run", "batch_job_id")

    # Drop batch_job table
    op.drop_index(op.f("ix_batch_job_project_id"), table_name="batch_job")
    op.drop_index(op.f("ix_batch_job_organization_id"), table_name="batch_job")
    op.drop_index(op.f("ix_batch_job_job_type"), table_name="batch_job")
    op.drop_table("batch_job")
