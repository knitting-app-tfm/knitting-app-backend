"""make pattern craft nullable

Revision ID: a1b2c3d4e5f6
Revises: 62c3b6acb675
Create Date: 2026-05-04 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "62c3b6acb675"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "patterns",
        "craft",
        existing_type=sa.Enum("KNITTING", "CROCHET", name="crafttype"),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "patterns",
        "craft",
        existing_type=sa.Enum("KNITTING", "CROCHET", name="crafttype"),
        nullable=False,
    )
