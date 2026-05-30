"""stock_movements.material_id nullable + material_name_snapshot column

Revision ID: 014_stock_movement_mat_null
Revises: 013_stock_movement_batch_id
Create Date: 2026-05-30

Relaxes `stock_movements.material_id` to nullable and adds a denormalized
`material_name_snapshot VARCHAR(255) NULL` column, so the admin-only
material force-delete can preserve ledger history when a material is
hard-deleted.

Workflow on force-delete (in `inventory.service.force_delete_material`):
  1. UPDATE stock_movements
       SET material_name_snapshot = <material.name>,
           material_id = NULL
     WHERE material_id = <id>
  2. DELETE the recipe rows + inventory row + material row.

The ledger row survives with the same quantity_change, reason, batch_id,
order_id, created_by, created_at — only the FK back-pointer to the now-
deleted material is severed, and the human-readable name is kept inline
for reports (`get_material_consumption_report` falls back to
material_name_snapshot when the join returns NULL).

Purely additive. No enum changes, no CAST risk, no backfill needed.
Existing rows keep their non-null material_id; the new column defaults to
NULL, which is fine because no force-delete has happened yet.

Revision id is 27 chars — comfortably under the `alembic_version.version_num`
varchar(32) cap that bit migration 009 (KNOWN_RISKS.md #1, #4).
"""
from alembic import op
import sqlalchemy as sa


revision = "014_stock_movement_mat_null"
down_revision = "013_stock_movement_batch_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "stock_movements",
        "material_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.add_column(
        "stock_movements",
        sa.Column("material_name_snapshot", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    # Downgrade is best-effort: succeeds only when no row has NULL
    # material_id (i.e. no force-delete has actually run). If any rows have
    # been NULLed by a force-delete, the ALTER COLUMN below raises and the
    # downgrade aborts — by design. Restore by backfilling material_id from
    # material_name_snapshot or accepting the data loss before retrying.
    op.drop_column("stock_movements", "material_name_snapshot")
    op.alter_column(
        "stock_movements",
        "material_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
