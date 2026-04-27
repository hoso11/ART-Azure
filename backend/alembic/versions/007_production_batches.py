"""add production_batches table and stock_based_production movement reason

Revision ID: 007_production_batches
Revises: 006_order_item_fulfillment
Create Date: 2026-04-27
"""
from alembic import op
import sqlalchemy as sa


revision = "007_production_batches"
down_revision = "006_order_item_fulfillment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # Postgres needs ALTER TYPE outside a transaction. SQLite stores enums as
    # CHECK constraints created from the SQLAlchemy model definitions, so the
    # new value is picked up automatically on table create — nothing to do.
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(
                "ALTER TYPE stockmovementreason "
                "ADD VALUE IF NOT EXISTS 'stock_based_production'"
            )

    op.create_table(
        "production_batches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("variant_id", sa.Integer(), sa.ForeignKey("product_variants.id"), nullable=False),
        sa.Column("quantity_to_produce", sa.Integer(), nullable=False),
        sa.Column("production_type", sa.String(20), nullable=False, server_default="stock_based"),
        sa.Column("current_stage", sa.String(50), nullable=False, server_default="cutting"),
        sa.Column("stage_status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("materials_deducted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("stock_added", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_production_batches_created_at", "production_batches", ["created_at"])
    op.create_index("ix_production_batches_stage_status", "production_batches", ["stage_status"])


def downgrade() -> None:
    op.drop_index("ix_production_batches_stage_status", "production_batches")
    op.drop_index("ix_production_batches_created_at", "production_batches")
    op.drop_table("production_batches")

    # Postgres cannot drop a single enum value without rewriting the type. We
    # leave the value in place on downgrade — having an unused enum label is
    # harmless and keeps downgrade safe.
