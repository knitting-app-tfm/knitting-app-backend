"""add calculated_grams_needed and calculated_skeins_needed to user_yarns

Revision ID: k2l3m4n5o6p7
Revises: j1e2f3a4b5c6
Create Date: 2026-06-13 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k2l3m4n5o6p7"
down_revision: Union[str, None] = "j1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_yarns", sa.Column("calculated_grams_needed", sa.Float(), nullable=True)
    )
    op.add_column(
        "user_yarns", sa.Column("calculated_skeins_needed", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("user_yarns", "calculated_skeins_needed")
    op.drop_column("user_yarns", "calculated_grams_needed")
