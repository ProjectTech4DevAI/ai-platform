"""add_embedding_batch_job_id_to_evaluation_run

Revision ID: a1b2c3d4e5f6
Revises: d5747495bd7c
Create Date: 2025-10-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "d5747495bd7c"
branch_labels = None
depends_on = None


def upgrade():
    # Add embedding_batch_job_id column to evaluation_run table
    op.add_column(
        "evaluation_run",
        sa.Column(
            "embedding_batch_job_id",
            sa.Integer(),
            nullable=True,
            comment="Reference to the batch_job for embedding-based similarity scoring",
        ),
    )

    # Add foreign key constraint to batch_job table
    op.create_foreign_key(
        "fk_evaluation_run_embedding_batch_job_id",
        "evaluation_run",
        "batch_job",
        ["embedding_batch_job_id"],
        ["id"],
    )


def downgrade():
    # Drop foreign key constraint
    op.drop_constraint(
        "fk_evaluation_run_embedding_batch_job_id",
        "evaluation_run",
        type_="foreignkey",
    )

    # Drop embedding_batch_job_id column
    op.drop_column("evaluation_run", "embedding_batch_job_id")
