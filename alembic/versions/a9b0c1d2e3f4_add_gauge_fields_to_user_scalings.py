"""add gauge fields to user_scalings

Revision ID: a9b0c1d2e3f4
Revises: b2c3d4e5f6a7
Create Date: 2026-06-11 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a9b0c1d2e3f4"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Temporary server_default fills any pre-existing rows; dropped immediately after.
    op.add_column(
        "user_scalings",
        sa.Column("gauge_stitches", sa.Float(), nullable=False, server_default="0"),
    )
    op.alter_column("user_scalings", "gauge_stitches", server_default=None)

    op.add_column(
        "user_scalings",
        sa.Column("gauge_rows", sa.Float(), nullable=True),
    )

    op.add_column(
        "user_scalings",
        sa.Column("gauge_size", sa.Float(), nullable=False, server_default="10"),
    )
    op.alter_column("user_scalings", "gauge_size", server_default=None)

    op.add_column(
        "user_scalings",
        sa.Column(
            "gauge_unit",
            sa.Enum("CM", "INCH", name="gaugeunit", create_type=False),
            nullable=False,
            server_default="CM",
        ),
    )
    op.alter_column("user_scalings", "gauge_unit", server_default=None)

    op.add_column(
        "user_scalings",
        sa.Column("needle_size", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_scalings", "needle_size")
    op.drop_column("user_scalings", "gauge_unit")
    op.drop_column("user_scalings", "gauge_size")
    op.drop_column("user_scalings", "gauge_rows")
    op.drop_column("user_scalings", "gauge_stitches")
