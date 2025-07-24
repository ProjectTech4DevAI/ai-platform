"""add openai_conversation table

Revision ID: ff579a9523c5
Revises: e8ee93526b37
Create Date: 2025-07-24 12:16:51.311014

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = "ff579a9523c5"
down_revision = "e8ee93526b37"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "openai_conversation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("response_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "ancestor_response_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column(
            "previous_response_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("user_question", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("response", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("model", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("assistant_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("inserted_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
    )
    op.create_index(
        op.f("ix_openai_conversation_ancestor_response_id"),
        "openai_conversation",
        ["ancestor_response_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_openai_conversation_previous_response_id"),
        "openai_conversation",
        ["previous_response_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_openai_conversation_response_id"),
        "openai_conversation",
        ["response_id"],
        unique=False,
    )
    op.create_foreign_key(
        None, "openai_conversation", "project", ["project_id"], ["id"]
    )
    op.create_foreign_key(
        None, "openai_conversation", "organization", ["organization_id"], ["id"]
    )


def downgrade():
    op.drop_index(
        op.f("ix_openai_conversation_response_id"), table_name="openai_conversation"
    )
    op.drop_index(
        op.f("ix_openai_conversation_previous_response_id"),
        table_name="openai_conversation",
    )
    op.drop_index(
        op.f("ix_openai_conversation_ancestor_response_id"),
        table_name="openai_conversation",
    )
    op.drop_table("openai_conversation")
