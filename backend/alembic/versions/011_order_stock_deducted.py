"""finished-stock deduction idempotency flag on orders

Revision ID: 011_order_stock_deducted
Revises: 010_batch_partial_outcome
Create Date: 2026-05-02

Adds a single non-destructive boolean column on `orders`:

- stock_deducted: BOOLEAN NOT NULL DEFAULT false

Set to true exactly once when an order transitions to status `completed`
and finished-product stock has been deducted from `product_variants.stock_quantity`.
The flag gates re-deduction so subsequent status changes (e.g.
completed -> draft -> completed) do not double-debit inventory.

`materials_deducted` is left untouched for historical compatibility.
This migration is INT/BOOL only — no enum changes, no CAST risk, server
default fills existing rows in a single ALTER (no backfill needed).
"""
from alembic import op
import sqlalchemy as sa


revision = "011_order_stock_deducted"
down_revision = "010_batch_partial_outcome"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "stock_deducted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("orders", "stock_deducted")
