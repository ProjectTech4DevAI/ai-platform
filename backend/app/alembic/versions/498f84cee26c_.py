"""empty message

Revision ID: 498f84cee26c
Revises: 904ed70e7dab, auto_add_prompt_table
Create Date: 2025-06-05 19:58:06.778925

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = '498f84cee26c'
down_revision = 'auto_add_prompt_table'
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
