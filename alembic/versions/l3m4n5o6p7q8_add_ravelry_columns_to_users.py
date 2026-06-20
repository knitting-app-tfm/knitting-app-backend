"""add ravelry_token and ravelry_username to users

Revision ID: l3m4n5o6p7q8
Revises: k2l3m4n5o6p7
Create Date: 2026-06-20 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "l3m4n5o6p7q8"
down_revision: Union[str, None] = "k2l3m4n5o6p7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("ravelry_token", sa.String(), nullable=True))
    op.add_column("users", sa.Column("ravelry_username", sa.String(), nullable=True))
    op.create_unique_constraint(
        "uq_users_ravelry_username", "users", ["ravelry_username"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_users_ravelry_username", "users", type_="unique")
    op.drop_column("users", "ravelry_username")
    op.drop_column("users", "ravelry_token")
