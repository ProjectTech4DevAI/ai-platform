"""add additional columns to model evaluation table

Revision ID: 06a8bed9e7a6
Revises: 72896bcc94da
Create Date: 2025-08-25 22:36:58.959768

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "06a8bed9e7a6"
down_revision = "72896bcc94da"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("model_evaluation", "testing_file_id")
    op.add_column(
        "model_evaluation",
        sa.Column(
            "test_data_s3_url", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
    )
    op.add_column(
        "model_evaluation",
        sa.Column(
            "prediction_data_s3_url", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
    )


def downgrade():
    op.drop_column("model_evaluation", "prediction_data_s3_url")
    op.drop_column("model_evaluation", "test_data_s3_url")
    op.add_column(
        "model_evaluation",
        sa.Column("testing_file_id", sa.VARCHAR(), autoincrement=False, nullable=True),
    )
