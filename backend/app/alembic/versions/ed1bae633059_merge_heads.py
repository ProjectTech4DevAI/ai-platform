"""merge heads

Revision ID: ed1bae633059
Revises: 38f0e8c8dc92, 93b86c1246b1
Create Date: 2025-08-29 13:51:29.080451

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'ed1bae633059'
down_revision = ('38f0e8c8dc92', '93b86c1246b1')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
