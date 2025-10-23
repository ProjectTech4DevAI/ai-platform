"""add_langfuse_trace_ids_to_evaluation_run

Revision ID: 2cc3c67356a8
Revises: a1b2c3d4e5f6
Create Date: 2025-10-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "2cc3c67356a8"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    # Add langfuse_trace_ids column to evaluation_run table
    op.add_column(
        "evaluation_run",
        sa.Column(
            "langfuse_trace_ids",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
            comment="Mapping of item_id to Langfuse trace_id for updating traces with scores",
        ),
    )


def downgrade():
    # Drop langfuse_trace_ids column
    op.drop_column("evaluation_run", "langfuse_trace_ids")
