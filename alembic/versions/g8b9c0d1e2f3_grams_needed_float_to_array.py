"""change grams_needed from float to float array

Revision ID: g8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-06-12 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "g8b9c0d1e2f3"
down_revision: Union[str, None] = "a9b0c1d2e3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "pattern_yarns",
        "grams_needed",
        type_=postgresql.ARRAY(sa.Float()),
        postgresql_using=(
            "CASE WHEN grams_needed IS NULL THEN NULL "
            "ELSE ARRAY[grams_needed]::float[] END"
        ),
        existing_nullable=True,
    )


def downgrade() -> None:
    # Collapse array back to a single float (take first element)
    op.alter_column(
        "pattern_yarns",
        "grams_needed",
        type_=sa.Float(),
        postgresql_using=(
            "CASE WHEN grams_needed IS NULL THEN NULL ELSE grams_needed[1] END"
        ),
        existing_nullable=True,
    )
