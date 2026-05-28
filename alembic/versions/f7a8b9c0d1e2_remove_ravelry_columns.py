"""remove ravelry columns from users and patterns

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-05-28 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "adb51820c83b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("users", "ravelry_token")
    op.drop_column("users", "ravelry_username")
    op.drop_column("patterns", "ravelry_pattern_id")
    op.drop_column("patterns", "tokens_file_path")


def downgrade() -> None:
    op.add_column("users", sa.Column("ravelry_token", sa.String(), nullable=True))
    op.add_column("users", sa.Column("ravelry_username", sa.String(), nullable=True))
    op.add_column(
        "patterns", sa.Column("ravelry_pattern_id", sa.String(), nullable=True)
    )
    op.add_column("patterns", sa.Column("tokens_file_path", sa.String(), nullable=True))
