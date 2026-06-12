"""add user_scalings table

Revision ID: b2c3d4e5f6a7
Revises: a0b1c2d3e4f5
Create Date: 2026-06-10 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a0b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_scalings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pattern_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("size_label", sa.String(), nullable=False),
        sa.Column("size_position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["pattern_id"], ["patterns.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pattern_id"),
    )


def downgrade() -> None:
    op.drop_table("user_scalings")
