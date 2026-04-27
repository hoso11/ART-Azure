"""add fulfilled_from_stock and production_quantity to order_items

Revision ID: 006_order_item_fulfillment
Revises: 004_order_materials_deducted
Create Date: 2026-04-27
"""
from alembic import op
import sqlalchemy as sa

revision = "006_order_item_fulfillment"
down_revision = "004_order_materials_deducted"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "order_items",
        sa.Column("fulfilled_from_stock", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "order_items",
        sa.Column("production_quantity", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("order_items", "production_quantity")
    op.drop_column("order_items", "fulfilled_from_stock")
