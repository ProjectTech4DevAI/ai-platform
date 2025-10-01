"""adding collection jobs table and altering collection table

Revision ID: 718dcc83f3b6
Revises: c6fb6d0b5897
Create Date: 2025-09-29 20:41:38.005505

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "718dcc83f3b6"
down_revision = "c6fb6d0b5897"
branch_labels = None
depends_on = None


collection_job_status_enum = postgresql.ENUM(
    "processing",
    "successful",
    "failed",
    name="collectionjobstatus",
    create_type=False,
)

collection_action_type = postgresql.ENUM(
    "create",
    "delete",
    name="collectionactiontype",
    create_type=False,
)


def upgrade():
    collection_job_status_enum.create(op.get_bind(), checkfirst=True)
    collection_action_type.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "collection_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("action_type", collection_action_type, nullable=False),
        sa.Column("collection_id", sa.Uuid(), nullable=True),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("status", collection_job_status_enum, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("inserted_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["collection_id"], ["collection.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.drop_constraint("collection_owner_id_fkey", "collection", type_="foreignkey")
    op.drop_column("collection", "owner_id")
    op.drop_column("collection", "status")
    op.drop_column("collection", "error_message")
    op.add_column("collection", sa.Column("inserted_at", sa.DateTime(), nullable=False))
    op.drop_column("collection", "created_at")


def downgrade():
    op.create_foreign_key(
        "openai_conversation_project_id_fkey1",
        "openai_conversation",
        "project",
        ["project_id"],
        ["id"],
    )
    op.create_foreign_key(
        "openai_conversation_organization_id_fkey1",
        "openai_conversation",
        "organization",
        ["organization_id"],
        ["id"],
    )
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
    op.drop_table("collection_jobs")
