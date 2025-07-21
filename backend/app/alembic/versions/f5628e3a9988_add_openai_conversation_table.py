"""your migration message

Revision ID: 8811e4d2fcf9
Revises: 4aa1f48c6321
Create Date: 2025-07-21 22:07:01.129760

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = "8811e4d2fcf9"
down_revision = "4aa1f48c6321"
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
        sa.Column(
            "assistant_response", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("model", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("assistant_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("inserted_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
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
