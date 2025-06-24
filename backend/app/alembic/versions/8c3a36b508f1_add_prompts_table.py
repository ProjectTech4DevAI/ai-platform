"""add prompts table

Revision ID: 8c3a36b508f1
Revises: 904ed70e7dab
Create Date: 2025-06-24 10:20:21.933351

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = '8c3a36b508f1'
down_revision = '904ed70e7dab'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('prompt',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('organization_id', sa.Integer(), nullable=False),
    sa.Column('inserted_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_prompt_name'), 'prompt', ['name'], unique=True)
    # ### end Alembic commands ###


def downgrade():
    op.drop_index(op.f('ix_prompt_name'), table_name='prompt')
    op.drop_table('prompt')
    # ### end Alembic commands ###