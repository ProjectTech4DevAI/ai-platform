"""adding collection job table and altering collections table

Revision ID: b30727137e65
Revises: c6fb6d0b5897
Create Date: 2025-10-05 14:19:14.213933

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "b30727137e65"
down_revision = "c6fb6d0b5897"
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
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("inserted_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["collection_id"], ["collection.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column("collection", sa.Column("inserted_at", sa.DateTime(), nullable=False))
    op.drop_constraint("collection_owner_id_fkey", "collection", type_="foreignkey")
    op.drop_column("collection", "owner_id")
    op.drop_column("collection", "created_at")
    op.drop_column("collection", "status")
    op.drop_column("collection", "error_message")


def downgrade():
    op.add_column(
        "collection",
        sa.Column("error_message", sa.VARCHAR(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "collection",
        sa.Column(
            "status",
            postgresql.ENUM(
                "processing", "successful", "failed", name="collectionstatus"
            ),
            server_default=sa.text("'processing'::collectionstatus"),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.add_column(
        "collection",
        sa.Column(
            "created_at", postgresql.TIMESTAMP(), autoincrement=False, nullable=False
        ),
    )
    op.add_column(
        "collection",
        sa.Column("owner_id", sa.INTEGER(), autoincrement=False, nullable=False),
    )
    op.create_foreign_key(
        "collection_owner_id_fkey",
        "collection",
        "user",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_column("collection", "inserted_at")
    op.drop_table("collection_jobs")
