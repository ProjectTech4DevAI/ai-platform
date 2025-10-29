"""add_evaluation_dataset_table_and_dataset_id_to_evaluation_run

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2025-10-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6g7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    # Create evaluation_dataset table
    op.create_table(
        "evaluation_dataset",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "dataset_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("s3_url", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "langfuse_dataset_id",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=True,
        ),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("inserted_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_evaluation_dataset_name"),
        "evaluation_dataset",
        ["name"],
        unique=False,
    )

    # Add dataset_id column to evaluation_run table
    op.add_column(
        "evaluation_run",
        sa.Column("dataset_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_evaluation_run_dataset_id",
        "evaluation_run",
        "evaluation_dataset",
        ["dataset_id"],
        ["id"],
    )


def downgrade():
    # Drop foreign key and column from evaluation_run
    op.drop_constraint(
        "fk_evaluation_run_dataset_id",
        "evaluation_run",
        type_="foreignkey",
    )
    op.drop_column("evaluation_run", "dataset_id")

    # Drop evaluation_dataset table
    op.drop_index(op.f("ix_evaluation_dataset_name"), table_name="evaluation_dataset")
    op.drop_table("evaluation_dataset")
