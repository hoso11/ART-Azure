"""partial outcome on production batches + damaged stock counter on variants

Revision ID: 010_batch_partial_outcome
Revises: 008_activity_log_columns
Create Date: 2026-04-28

Phase 1 of the Խոտան (defective) feature — stock-based batches only.

production_batches gains two integer counters and a free-text reason:
- good_quantity:    INT NOT NULL DEFAULT 0 — units that pass QC
- damaged_quantity: INT NOT NULL DEFAULT 0 — units rejected as Խոտան
- defect_reason:    TEXT NULL              — optional admin note about the damage

product_variants gains one counter:
- damaged_stock_quantity: INT NOT NULL DEFAULT 0 — running total of defective units

All INT/TEXT — no enum, no CAST, no varchar(32) revision-id risk. Server
defaults so existing rows are valid without backfill.
"""
from alembic import op
import sqlalchemy as sa


revision = "010_batch_partial_outcome"
down_revision = "008_activity_log_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "production_batches",
        sa.Column(
            "good_quantity",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "production_batches",
        sa.Column(
            "damaged_quantity",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "production_batches",
        sa.Column("defect_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "product_variants",
        sa.Column(
            "damaged_stock_quantity",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("product_variants", "damaged_stock_quantity")
    op.drop_column("production_batches", "defect_reason")
    op.drop_column("production_batches", "damaged_quantity")
    op.drop_column("production_batches", "good_quantity")
