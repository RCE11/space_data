"""enable row level security on all tables

Revision ID: 529bf6dd2754
Revises: 941ba92e9c91
Create Date: 2026-04-01 08:24:13.798562

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '529bf6dd2754'
down_revision: Union[str, Sequence[str], None] = '941ba92e9c91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    tables = ["operators", "satellites", "orbits", "launches", "api_keys", "request_log"]
    for table in tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    """Downgrade schema."""
    tables = ["operators", "satellites", "orbits", "launches", "api_keys", "request_log"]
    for table in tables:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
