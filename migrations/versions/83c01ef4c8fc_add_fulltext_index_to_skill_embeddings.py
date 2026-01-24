"""add_fulltext_index_to_skill_embeddings

Revision ID: 83c01ef4c8fc
Revises: c5fc18e7c719
Create Date: 2026-01-24 03:35:29.681937

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '83c01ef4c8fc'
down_revision: Union[str, Sequence[str], None] = 'c5fc18e7c719'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add full-text search GIN index and skill_file_id index to skill_embeddings."""
    # GIN index for full-text search on chunk_text
    op.execute("""
        CREATE INDEX ix_skill_embeddings_chunk_text_fts
        ON skill_embeddings
        USING GIN (to_tsvector('english', chunk_text))
    """)

    # Index on skill_file_id for efficient joins
    op.create_index(
        "ix_skill_embeddings_skill_file_id",
        "skill_embeddings",
        ["skill_file_id"],
    )


def downgrade() -> None:
    """Remove full-text search GIN index and skill_file_id index."""
    op.drop_index("ix_skill_embeddings_skill_file_id", table_name="skill_embeddings")
    op.execute("DROP INDEX ix_skill_embeddings_chunk_text_fts")
