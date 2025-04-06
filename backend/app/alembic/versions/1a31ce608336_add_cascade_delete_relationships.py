"""Add cascade delete relationships

Revision ID: 1a31ce608336
Revises: d98dd8ec85a3
Create Date: 2024-07-31 22:24:34.447891

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = "1a31ce608336"
down_revision = "d98dd8ec85a3"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column("item", "owner_id", existing_type=sa.UUID(), nullable=False)
    op.drop_constraint("item_owner_id_fkey", "item", type_="foreignkey")
    op.create_foreign_key(
        None, "item", "user", ["owner_id"], ["id"], ondelete="CASCADE"
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, "item", type_="foreignkey")
    op.create_foreign_key("item_owner_id_fkey", "item", "user", ["owner_id"], ["id"])
    op.alter_column("item", "owner_id", existing_type=sa.UUID(), nullable=True)
    # ### end Alembic commands ###
