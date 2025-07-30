"""add fine tuning and model evaluation table

Revision ID: 8c477031ccd7
Revises: e9dd35eff62c
Create Date: 2025-07-30 22:58:22.671782

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "8c477031ccd7"
down_revision = "e9dd35eff62c"
branch_labels = None
depends_on = None

evaluation_status_enum = postgresql.ENUM(
    "pending",
    "running",
    "completed",
    "failed",
    name="evaluationstatus",
    create_type=False,  # we create manually to avoid duplicate issues
)


def upgrade():
    evaluation_status_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "fine_tuning",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("base_model", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("split_ratio", type_=sa.Float(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column(
            "training_file_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("testing_file_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("openai_job_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "fine_tuned_model", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
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
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fine_tuning_id", sa.Integer(), nullable=False),
        sa.Column("model_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("eval_split_ratio", type_=sa.Float(), nullable=False),
        sa.Column("metric", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("score", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "status", evaluation_status_enum, nullable=False, server_default="pending"
        ),
        sa.Column("is_best_model", sa.Boolean, nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
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
