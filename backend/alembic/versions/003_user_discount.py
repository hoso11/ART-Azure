"""Add discount_percent to users

Revision ID: 003_user_discount
Revises: 002_var_mat_req
Create Date: 2026-04-27
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003_user_discount"
down_revision: Union[str, None] = "002_var_mat_req"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("discount_percent", sa.Numeric(5, 2), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("users", "discount_percent")
