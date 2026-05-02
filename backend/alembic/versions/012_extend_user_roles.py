"""extend userrole enum with director / production_manager / warehouse_manager

Revision ID: 012_extend_user_roles
Revises: 011_order_stock_deducted
Create Date: 2026-05-02

Adds three new values to the existing `userrole` Postgres ENUM (defined in
001_initial.py as `sa.Enum("admin", "simple_user", name="userrole")`).

Non-destructive:
- Existing rows are untouched. `admin` and `simple_user` remain valid.
- IF NOT EXISTS makes the migration idempotent.

Downgrade is a documented no-op:
- Postgres ENUMs do not support removing a value with `ALTER TYPE … DROP VALUE`.
- Reverting would require: UPDATE users SET role='simple_user' WHERE role NOT
  IN ('admin','simple_user'); then drop the column, drop the type, recreate
  the type with the original two values, recreate the column, restore data.
- That sequence is destructive and risky in production. We accept the new
  values as forward-only.
"""
from alembic import op


revision = "012_extend_user_roles"
down_revision = "011_order_stock_deducted"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'director'")
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'production_manager'")
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'warehouse_manager'")


def downgrade() -> None:
    # Postgres ENUM values cannot be removed without recreating the type.
    # Documented no-op; see module docstring.
    pass
