"""add fine tuning and model evaluation table

Revision ID: 6ed6ed401847
Revises: 40307ab77e9f
Create Date: 2025-09-01 14:54:03.553608

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


finetuning_status_enum = postgresql.ENUM(
    "pending",
    "running",
    "completed",
    "failed",
    name="finetuningstatus",
    create_type=False,
)

modelevaluation_status_enum = postgresql.ENUM(
    "pending",
    "running",
    "completed",
    "failed",
    name="modelevaluationstatus",
    create_type=False,
)


def upgrade():
    finetuning_status_enum.create(op.get_bind(), checkfirst=True)
    modelevaluation_status_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "fine_tuning",
        sa.Column("base_model", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("split_ratio", sa.Float(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column(
            "training_file_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider_job_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "status",
            finetuning_status_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "fine_tuned_model", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column(
            "train_data_s3_object", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column(
            "test_data_s3_object", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("error_message", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("inserted_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["document.id"],
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "model_evaluation",
        sa.Column("fine_tuning_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column(
            "fine_tuned_model", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column(
            "test_data_s3_object", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("base_model", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("split_ratio", sa.Float(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("score", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "prediction_data_s3_object",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=True,
        ),
        sa.Column(
            "status",
            modelevaluation_status_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_message", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("inserted_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["document.id"],
        ),
        sa.ForeignKeyConstraint(
            ["fine_tuning_id"], ["fine_tuning.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("model_evaluation")
    op.drop_table("fine_tuning")
