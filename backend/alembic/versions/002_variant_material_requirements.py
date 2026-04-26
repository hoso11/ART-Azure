"""Add variant material requirements table

Revision ID: 002_variant_material_requirements
Revises: 001_initial
Create Date: 2026-04-26

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002_variant_material_requirements"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "variant_material_requirements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("variant_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("quantity_per_item", sa.Numeric(10, 3), nullable=False),
        sa.ForeignKeyConstraint(["variant_id"], ["product_variants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("variant_id", "material_id", name="uq_variant_material"),
    )
    op.create_index(
        "ix_variant_material_requirements_variant_id",
        "variant_material_requirements",
        ["variant_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_variant_material_requirements_variant_id", table_name="variant_material_requirements")
    op.drop_table("variant_material_requirements")
