"""add prompt table

Revision ID: auto_add_prompt_table
Revises: 
Create Date: 2024-06-10

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

# revision identifiers, used by Alembic.
revision = "auto_add_prompt_table"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "prompt",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

def downgrade():
    op.drop_table("prompt") 