"""add materials_deducted to orders

Revision ID: 004_order_materials_deducted
Revises: 003_user_discount
Create Date: 2026-04-27
"""

from alembic import op
import sqlalchemy as sa

revision = "004_order_materials_deducted"
down_revision = "003_user_discount"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "orders",
        sa.Column("materials_deducted", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade():
    op.drop_column("orders", "materials_deducted")
