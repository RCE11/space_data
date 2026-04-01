"""hash api keys add key_hash and key_prefix drop plaintext key

Revision ID: 941ba92e9c91
Revises: 7acf879a34d7
Create Date: 2026-03-31 17:07:41.264459

"""
import hashlib
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '941ba92e9c91'
down_revision: Union[str, Sequence[str], None] = '7acf879a34d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns (nullable initially so we can populate them)
    op.add_column("api_keys", sa.Column("key_hash", sa.String(64)))
    op.add_column("api_keys", sa.Column("key_prefix", sa.String(12)))

    # Populate from existing plaintext keys
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, key FROM api_keys")).fetchall()
    for row in rows:
        key_hash = hashlib.sha256(row.key.encode()).hexdigest()
        key_prefix = row.key[:12]
        conn.execute(
            sa.text("UPDATE api_keys SET key_hash = :h, key_prefix = :p WHERE id = :id"),
            {"h": key_hash, "p": key_prefix, "id": row.id},
        )

    # Now make key_hash non-nullable, unique, and indexed
    op.alter_column("api_keys", "key_hash", nullable=False)
    op.create_unique_constraint("uq_api_keys_key_hash", "api_keys", ["key_hash"])
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"])

    # Drop the plaintext key column and its index
    op.drop_index("ix_api_keys_key", table_name="api_keys")
    op.drop_column("api_keys", "key")


def downgrade() -> None:
    # Re-add the plaintext key column (data will be lost — keys cannot be recovered)
    op.add_column("api_keys", sa.Column("key", sa.String(64)))
    op.create_unique_constraint("uq_api_keys_key", "api_keys", ["key"])
    op.create_index("ix_api_keys_key", "api_keys", ["key"])

    op.drop_index("ix_api_keys_key_hash", table_name="api_keys")
    op.drop_constraint("uq_api_keys_key_hash", "api_keys", type_="unique")
    op.drop_column("api_keys", "key_prefix")
    op.drop_column("api_keys", "key_hash")
