"""adding collection job table and altering collections table

Revision ID: b30727137e65
Revises: 7ab577d3af26
Create Date: 2025-10-05 14:19:14.213933

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "b30727137e65"
down_revision = "7ab577d3af26"
branch_labels = None
depends_on = None

collection_job_status_enum = postgresql.ENUM(
    "PENDING",
    "PROCESSING",
    "SUCCESSFUL",
    "FAILED",
    name="collectionjobstatus",
    create_type=False,
)

collection_action_type = postgresql.ENUM(
    "CREATE",
    "DELETE",
    name="collectionactiontype",
    create_type=False,
)


def upgrade():
    collection_job_status_enum.create(op.get_bind(), checkfirst=True)
    collection_action_type.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "collection_jobs",
        sa.Column("action_type", collection_action_type, nullable=False),
        sa.Column("collection_id", sa.Uuid(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("status", collection_job_status_enum, nullable=False),
        sa.Column("task_id", sa.String(), nullable=True),
        sa.Column("trace_id", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("inserted_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["collection_id"], ["collection.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.alter_column("collection", "created_at", new_column_name="inserted_at")
    op.alter_column(
        "collection", "llm_service_id", existing_type=sa.VARCHAR(), nullable=False
    )
    op.alter_column(
        "collection", "llm_service_name", existing_type=sa.VARCHAR(), nullable=False
    )
    op.drop_constraint("collection_owner_id_fkey", "collection", type_="foreignkey")
    op.drop_column("collection", "owner_id")
    op.drop_column("collection", "status")
    op.drop_column("collection", "error_message")


def downgrade():
    op.add_column(
        "collection",
        sa.Column("error_message", sa.VARCHAR(), autoincrement=False, nullable=True),
    )
    collectionstatus = postgresql.ENUM(
        "processing", "successful", "failed", name="collectionstatus"
    )

    op.add_column(
        "collection",
        sa.Column(
            "status",
            collectionstatus,
            server_default=sa.text("'processing'::collectionstatus"),
            nullable=True,
        ),
    )
    op.add_column(
        "collection",
        sa.Column("owner_id", sa.Integer(), nullable=True),
    )

    op.execute("UPDATE collection SET status = 'processing' WHERE status IS NULL")
    op.execute("UPDATE collection SET owner_id = 1 WHERE owner_id IS NULL")
    op.create_foreign_key(
        "collection_owner_id_fkey",
        "collection",
        "user",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.alter_column("collection", "status", nullable=False)
    op.alter_column("collection", "owner_id", nullable=False)
    op.alter_column("collection", "inserted_at", new_column_name="created_at")
    op.alter_column(
        "collection", "llm_service_name", existing_type=sa.VARCHAR(), nullable=True
    )
    op.alter_column(
        "collection", "llm_service_id", existing_type=sa.VARCHAR(), nullable=True
    )
    op.drop_table("collection_jobs")
