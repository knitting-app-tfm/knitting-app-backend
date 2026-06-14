"""create user_yarns table

Revision ID: h9c0d1e2f3a4
Revises: g8b9c0d1e2f3
Create Date: 2026-06-12 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "h9c0d1e2f3a4"
down_revision: Union[str, None] = "g8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE user_yarns (
            id UUID PRIMARY KEY,
            pattern_yarn_id UUID NOT NULL REFERENCES pattern_yarns(id),
            label VARCHAR,
            yarn_weight yarnweight,
            meters_per_unit DOUBLE PRECISION,
            grams_per_unit DOUBLE PRECISION,
            strands INTEGER NOT NULL DEFAULT 1
        )
    """)


def downgrade() -> None:
    op.drop_table("user_yarns")
