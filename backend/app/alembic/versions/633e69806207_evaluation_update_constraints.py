"""evaluation update constraints

Revision ID: 633e69806207
Revises: 6fe772038a5a
Create Date: 2025-11-13 11:36:16.484694

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "633e69806207"
down_revision = "6fe772038a5a"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "evaluation_run",
        "config",
        existing_type=postgresql.JSON(astext_type=sa.Text()),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=False,
    )
    op.alter_column(
        "evaluation_run",
        "score",
        existing_type=postgresql.JSON(astext_type=sa.Text()),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=True,
    )
    # Remove SET NULL behavior from evaluation_run batch_job foreign keys
    # This ensures evaluation runs fail if their batch job is deleted (maintain referential integrity)
    op.drop_constraint(
        "fk_evaluation_run_embedding_batch_job_id", "evaluation_run", type_="foreignkey"
    )
    op.drop_constraint(
        "evaluation_run_batch_job_id_fkey", "evaluation_run", type_="foreignkey"
    )
    op.drop_constraint(
        "openai_conversation_organization_id_fkey1",
        "openai_conversation",
        type_="foreignkey",
    )
    op.drop_constraint(
        "openai_conversation_project_id_fkey1",
        "openai_conversation",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "evaluation_run_batch_job_id_fkey",
        "evaluation_run",
        "batch_job",
        ["batch_job_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_evaluation_run_embedding_batch_job_id",
        "evaluation_run",
        "batch_job",
        ["embedding_batch_job_id"],
        ["id"],
    )


def downgrade():
    op.alter_column(
        "evaluation_run",
        "score",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=postgresql.JSON(astext_type=sa.Text()),
        existing_nullable=True,
    )
    op.alter_column(
        "evaluation_run",
        "config",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=postgresql.JSON(astext_type=sa.Text()),
        existing_nullable=False,
    )
    # Restore SET NULL behavior to evaluation_run batch_job foreign keys
    op.drop_constraint(
        "fk_evaluation_run_embedding_batch_job_id", "evaluation_run", type_="foreignkey"
    )
    op.drop_constraint(
        "evaluation_run_batch_job_id_fkey", "evaluation_run", type_="foreignkey"
    )
    op.create_foreign_key(
        "evaluation_run_batch_job_id_fkey",
        "evaluation_run",
        "batch_job",
        ["batch_job_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_evaluation_run_embedding_batch_job_id",
        "evaluation_run",
        "batch_job",
        ["embedding_batch_job_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "openai_conversation_organization_id_fkey1",
        "openai_conversation",
        "organization",
        ["organization_id"],
        ["id"],
    )
    op.create_foreign_key(
        "openai_conversation_project_id_fkey1",
        "openai_conversation",
        "project",
        ["project_id"],
        ["id"],
    )
