"""stock_movements.batch_id back-pointer for batch rollback

Revision ID: 013_stock_movement_batch_id
Revises: 012_extend_user_roles
Create Date: 2026-05-29

Adds a nullable FK from `stock_movements` to `production_batches` so that
the new admin-only delete-batch flow can identify which ledger rows were
written by a specific batch and append the matching reversals.

This is INT/FK only — no enum changes, no CAST risk, no backfill. Existing
rows keep `batch_id = NULL` (legacy, pre-v38 batches; their material
deductions cannot be rolled back by the new endpoint — by design, the
service refuses with code="batch_legacy_no_movement_link").

`ondelete=SET NULL` on the FK: when a batch is hard-deleted by the new
rollback service, the original + reversal stock_movements survive as
ledger entries with batch_id nulled out. Material-consumption reports
continue to show both rows with their respective reasons.
"""
from alembic import op
import sqlalchemy as sa


revision = "013_stock_movement_batch_id"
down_revision = "012_extend_user_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stock_movements",
        sa.Column("batch_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_stock_movements_batch_id_production_batches",
        "stock_movements",
        "production_batches",
        ["batch_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_stock_movements_batch_id",
        "stock_movements",
        ["batch_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_stock_movements_batch_id", table_name="stock_movements")
    op.drop_constraint(
        "fk_stock_movements_batch_id_production_batches",
        "stock_movements",
        type_="foreignkey",
    )
    op.drop_column("stock_movements", "batch_id")
