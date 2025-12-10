"""add/alter columns in collections table

Revision ID: 3389c67fdcb4
Revises: 8757b005d681
Create Date: 2025-06-20 18:08:16.585843

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '017'
down_revision = '016'
branch_labels = None
depends_on = None

collection_status_enum = postgresql.ENUM(
    "processing",
    "successful",
    "failed",
    name="collectionstatus",
    create_type=False,  # we create manually to avoid duplicate issues
)


def upgrade():
    collection_status_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "collection", sa.Column("organization_id", sa.Integer(), nullable=False)
    )
    op.add_column("collection", sa.Column("project_id", sa.Integer(), nullable=True))
    op.add_column(
        "collection",
        sa.Column(
            "status",
            collection_status_enum,
            nullable=False,
            server_default="processing",
        ),
    )
    op.add_column("collection", sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.alter_column(
        "collection", "llm_service_id", existing_type=sa.VARCHAR(), nullable=True
    )
    op.alter_column(
        "collection", "llm_service_name", existing_type=sa.VARCHAR(), nullable=True
    )
    op.create_foreign_key(
        None,
        "collection",
        "organization",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        None, "collection", "project", ["project_id"], ["id"], ondelete="CASCADE"
    )


def downgrade():
    op.drop_constraint(None, "collection", type_="foreignkey")
    op.drop_constraint(None, "collection", type_="foreignkey")
    op.alter_column(
        "collection", "llm_service_name", existing_type=sa.VARCHAR(), nullable=False
    )
    op.alter_column(
        "collection", "llm_service_id", existing_type=sa.VARCHAR(), nullable=False
    )
    op.drop_column("collection", "updated_at")
    op.drop_column("collection", "status")
    op.drop_column("collection", "project_id")
    op.drop_column("collection", "organization_id")
