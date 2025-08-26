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

modelevaluation_status_enum = postgresql.ENUM(
    "pending",
    "running",
    "completed",
    "failed",
    name="modelevaluationstatus",
    create_type=False,
)


def upgrade():
    op.add_column(
        "model_evaluation",
        sa.Column("test_data_url", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    )
    op.add_column(
        "model_evaluation",
        sa.Column("batch_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.add_column(
        "model_evaluation",
        sa.Column("output_file_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.add_column(
        "model_evaluation",
        sa.Column("batch_status", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.add_column(
        "model_evaluation",
        sa.Column(
            "prediction_data_url", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
    )
    sa.Column(
        "eval_status",
        modelevaluation_status_enum,
        nullable=False,
        server_default="pending",
    )
    op.alter_column(
        "model_evaluation", "testing_file_id", existing_type=sa.VARCHAR(), nullable=True
    )
    op.drop_column("model_evaluation", "status")


def downgrade():
    op.add_column(
        "model_evaluation",
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "running",
                "completed",
                "failed",
                name="modelevaluationstatus",
            ),
            server_default=sa.text("'pending'::modelevaluationstatus"),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.alter_column(
        "model_evaluation",
        "testing_file_id",
        existing_type=sa.VARCHAR(),
        nullable=False,
    )
    op.drop_column("model_evaluation", "eval_status")
    op.drop_column("model_evaluation", "prediction_data_url")
    op.drop_column("model_evaluation", "batch_status")
    op.drop_column("model_evaluation", "output_file_id")
    op.drop_column("model_evaluation", "batch_id")
    op.drop_column("model_evaluation", "test_data_url")
