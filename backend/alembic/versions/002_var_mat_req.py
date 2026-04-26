"""Add product size material requirements table

Revision ID: 002_var_mat_req
Revises: 001_initial
Create Date: 2026-04-26

Each row stores: product + size + material + qty_per_item.
When a variant's stock_quantity increases by N the system looks up rows
matching (product_id, variant.size) and deducts N*qty_per_item from inventory.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002_var_mat_req"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product_size_material_requirements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("size", sa.String(50), nullable=False),
        sa.Column("quantity_per_item", sa.Numeric(10, 3), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "material_id", "size", name="uq_product_material_size"),
    )
    op.create_index(
        "ix_product_size_material_requirements_product_id",
        "product_size_material_requirements",
        ["product_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_product_size_material_requirements_product_id",
        table_name="product_size_material_requirements",
    )
    op.drop_table("product_size_material_requirements")
