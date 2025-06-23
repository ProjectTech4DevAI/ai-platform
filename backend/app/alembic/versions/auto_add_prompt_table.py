"""add prompt table

Revision ID: auto_add_prompt_table
Revises: 904ed70e7dab
Create Date: 2024-06-10

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

# revision identifiers, used by Alembic.
revision = "auto_add_prompt_table"
down_revision = "904ed70e7dab"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "prompt",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("inserted_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], name="prompt_organization_id_fkey", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], name="prompt_project_id_fkey", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

def downgrade():
    op.drop_table("prompt") 