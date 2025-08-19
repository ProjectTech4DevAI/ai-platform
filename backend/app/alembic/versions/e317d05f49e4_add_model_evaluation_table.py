"""add model evaluation table

Revision ID: e317d05f49e4
Revises: db9b5413d3ce
Create Date: 2025-08-10 21:36:07.863951

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "e317d05f49e4"
down_revision = "db9b5413d3ce"
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
    modelevaluation_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "model_evaluation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.Column("fine_tuning_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["fine_tuning_id"], ["fine_tuning.id"], ondelete="CASCADE"
        ),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["document.id"]),
        sa.Column("model_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "testing_file_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("base_model", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("split_ratio", sa.Float(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("score", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "status",
            modelevaluation_status_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_message", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], ondelete="CASCADE"
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("inserted_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table("model_evaluation")
