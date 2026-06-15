"""remove null elements from grams_needed arrays

Revision ID: j1e2f3a4b5c6
Revises: h9c0d1e2f3a4
Create Date: 2026-06-12 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "j1e2f3a4b5c6"
down_revision: Union[str, None] = "h9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Strip NULL elements from any grams_needed array; set to NULL if nothing remains.
    op.execute("""
        UPDATE pattern_yarns
        SET grams_needed = CASE
            WHEN array_length(
                ARRAY(SELECT elem FROM unnest(grams_needed) AS t(elem) WHERE elem IS NOT NULL),
                1
            ) IS NULL THEN NULL
            ELSE ARRAY(SELECT elem FROM unnest(grams_needed) AS t(elem) WHERE elem IS NOT NULL)
        END
        WHERE grams_needed IS NOT NULL
    """)


def downgrade() -> None:
    pass
