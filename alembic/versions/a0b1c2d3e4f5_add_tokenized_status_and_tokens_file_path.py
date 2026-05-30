"""add TOKENIZED to patternstatus enum and tokens_file_path column

Revision ID: a0b1c2d3e4f5
Revises: f7a8b9c0d1e2
Create Date: 2026-05-30 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a0b1c2d3e4f5"
down_revision: Union[str, Sequence[str], None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE patternstatus ADD VALUE IF NOT EXISTS 'TOKENIZED'")
    op.add_column("patterns", sa.Column("tokens_file_path", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("patterns", "tokens_file_path")
    # Note: removing a value from a PostgreSQL enum requires recreating the type.
    # The TOKENIZED value is intentionally left in the patternstatus enum on downgrade.
