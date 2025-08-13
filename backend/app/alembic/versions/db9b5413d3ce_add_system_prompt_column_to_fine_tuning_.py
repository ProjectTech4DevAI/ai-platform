"""add system prompt column to fine tuning table

Revision ID: db9b5413d3ce
Revises: e3c74fab4356
Create Date: 2025-08-06 20:32:32.454567

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = "db9b5413d3ce"
down_revision = "e3c74fab4356"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("fine_tuning", sa.Column("system_prompt", sa.Text(), nullable=False))


def downgrade():
    op.drop_column("fine_tuning", "system_prompt")
