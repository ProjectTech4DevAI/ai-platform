"""alter doc transform table for celery

Revision ID: 039
Revises: 038
Create Date: 2025-11-12 20:08:39.774862

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "039"
down_revision = "038"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "doc_transformation_job",
        sa.Column("task_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.add_column(
        "doc_transformation_job",
        sa.Column("trace_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.alter_column(
        "doc_transformation_job", "created_at", new_column_name="inserted_at"
    )


def downgrade():
    op.alter_column(
        "doc_transformation_job", "inserted_at", new_column_name="created_at"
    )
    op.drop_column("doc_transformation_job", "trace_id")
    op.drop_column("doc_transformation_job", "task_id")
