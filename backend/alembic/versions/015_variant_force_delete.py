"""order_items + production_batches variant_id nullable + name snapshots

Revision ID: 015_variant_force_delete
Revises: 014_stock_movement_mat_null
Create Date: 2026-05-31

Relaxes the variant FK on the two tables that block admin variant
hard-delete today and adds denormalized snapshot columns so historical
orders and production batches stay readable after the underlying
ProductVariant row is gone.

Workflow on force-delete (in `products.service.force_delete_variant`):
  1. UPDATE order_items
       SET variant_name_snapshot  = "<size> / <color>",
           product_name_snapshot  = <product.name>,
           product_variant_id     = NULL
     WHERE product_variant_id = <id>
  2. UPDATE production_batches
       SET variant_name_snapshot  = "<size> / <color>",
           product_name_snapshot  = <product.name>,
           variant_id             = NULL
     WHERE variant_id = <id>
  3. DELETE the ProductVariant row.

Ledger and order rows survive with the same quantities and unit_price;
only the FK back-pointer to the now-deleted variant is severed and the
human-readable name is kept inline. Order detail views, production
detail views, and any report that joins through this FK fall back to
the snapshot + `(ջնջված)` marker.

Purely additive. No enum changes, no CAST risk, no backfill needed.
Existing rows keep their non-null FK; the new snapshot columns default
to NULL because no force-delete has happened yet.

Revision id is 27 chars — comfortably under the `alembic_version.version_num`
varchar(32) cap that bit migration 009 (KNOWN_RISKS.md #1, #4).
"""
from alembic import op
import sqlalchemy as sa


revision = "015_variant_force_delete"
down_revision = "014_stock_movement_mat_null"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "order_items",
        "product_variant_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.add_column(
        "order_items",
        sa.Column("variant_name_snapshot", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "order_items",
        sa.Column("product_name_snapshot", sa.String(length=255), nullable=True),
    )

    op.alter_column(
        "production_batches",
        "variant_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.add_column(
        "production_batches",
        sa.Column("variant_name_snapshot", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "production_batches",
        sa.Column("product_name_snapshot", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    # Downgrade is best-effort: succeeds only when no row has been NULLed
    # by a force-delete. If any orphans exist, the ALTER COLUMN below
    # raises and the downgrade aborts — by design. Restore by backfilling
    # the FK column from the snapshot or accepting the data loss before
    # retrying. Same forward-only caveat as migration 014.
    op.drop_column("production_batches", "product_name_snapshot")
    op.drop_column("production_batches", "variant_name_snapshot")
    op.alter_column(
        "production_batches",
        "variant_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.drop_column("order_items", "product_name_snapshot")
    op.drop_column("order_items", "variant_name_snapshot")
    op.alter_column(
        "order_items",
        "product_variant_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
