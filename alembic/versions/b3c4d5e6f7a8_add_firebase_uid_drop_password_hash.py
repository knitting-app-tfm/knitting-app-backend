"""add firebase_uid drop password_hash

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-05-16 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("users", "password_hash")
    op.add_column("users", sa.Column("firebase_uid", sa.String(), nullable=True))
    op.execute("UPDATE users SET firebase_uid = id::text WHERE firebase_uid IS NULL")
    op.alter_column("users", "firebase_uid", nullable=False)
    op.create_unique_constraint("uq_users_firebase_uid", "users", ["firebase_uid"])


def downgrade() -> None:
    op.drop_constraint("uq_users_firebase_uid", "users", type_="unique")
    op.drop_column("users", "firebase_uid")
    op.add_column("users", sa.Column("password_hash", sa.String(), nullable=True))
