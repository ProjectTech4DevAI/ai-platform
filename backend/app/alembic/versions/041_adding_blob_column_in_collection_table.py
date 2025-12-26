"""adding blob column in collection table

Revision ID: 041
Revises: 040
Create Date: 2025-12-24 11:03:44.620424

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "041"
down_revision = "040"
branch_labels = None
depends_on = None

provider_enum = postgresql.ENUM(
    "openai",
    name="providertype",
    create_type=True,
)


def upgrade():
    provider_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "collection",
        sa.Column(
            "collection_blob",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Provider-specific collection parameters (name, description, chunking params etc.)",
        ),
    )

    op.add_column(
        "collection",
        sa.Column(
            "provider",
            provider_enum,
            nullable=True,
            comment="LLM provider used for this collection (e.g., 'openai', 'bedrock', 'gemini')",
        ),
    )

    op.execute("UPDATE collection SET provider = 'openai' WHERE provider IS NULL")

    op.alter_column(
        "collection",
        "provider",
        nullable=False,
        existing_type=provider_enum,
    )

    op.alter_column(
        "collection",
        "llm_service_name",
        existing_type=sa.VARCHAR(),
        comment="Name of the LLM service",
        existing_comment="Name of the LLM provider's service",
        existing_nullable=False,
    )


def downgrade():
    op.alter_column(
        "collection",
        "llm_service_name",
        existing_type=sa.VARCHAR(),
        comment="Name of the LLM service provider",
        existing_comment="Name of the LLM service",
        existing_nullable=False,
    )
    op.drop_column("collection", "provider")
    op.drop_column("collection", "collection_blob")
