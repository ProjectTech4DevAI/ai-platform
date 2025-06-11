"""create assistant table

Revision ID: 8eefcfedc409
Revises: 904ed70e7dab
Create Date: 2025-06-11 11:48:42.340144

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = "8eefcfedc409"
down_revision = "904ed70e7dab"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "openai_assistant",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assistant_id", sa.VARCHAR(length=255), nullable=False),
        sa.Column("name", sa.VARCHAR(length=255), nullable=False),
        sa.Column("max_num_results", sa.Integer, nullable=False),
        sa.Column("model", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=False),
        sa.Column("vector_store_id", sa.VARCHAR(length=255), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("inserted_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("openai_assistant")
