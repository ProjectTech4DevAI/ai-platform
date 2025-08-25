"""add data to s3 url columns

Revision ID: 72896bcc94da
Revises: e317d05f49e4
Create Date: 2025-08-22 00:44:45.426211

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = "72896bcc94da"
down_revision = "e317d05f49e4"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("fine_tuning", "testing_file_id")
    op.add_column(
        "fine_tuning",
        sa.Column("train_data_url", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.add_column(
        "fine_tuning",
        sa.Column("test_data_url", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )


def downgrade():
    op.drop_column("fine_tuning", "test_data_url")
    op.drop_column("fine_tuning", "train_data_url")
    op.add_column(
        "fine_tuning",
        sa.Column("testing_file_id", sa.VARCHAR(), autoincrement=False, nullable=True),
    )
