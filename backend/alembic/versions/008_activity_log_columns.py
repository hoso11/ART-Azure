"""extend activity_logs with audit columns (user_email, old/new values, details, ip)

Revision ID: 008_activity_log_columns
Revises: 007_production_batches
Create Date: 2026-04-27
"""
from alembic import op
import sqlalchemy as sa


revision = "008_activity_log_columns"
down_revision = "007_production_batches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("activity_logs", sa.Column("user_email", sa.String(255), nullable=True))
    op.add_column("activity_logs", sa.Column("old_values", sa.JSON(), nullable=True))
    op.add_column("activity_logs", sa.Column("new_values", sa.JSON(), nullable=True))
    op.add_column("activity_logs", sa.Column("details", sa.Text(), nullable=True))
    op.add_column("activity_logs", sa.Column("ip_address", sa.String(45), nullable=True))

    # Failed-login rows have no authenticated user.
    op.alter_column("activity_logs", "user_id", existing_type=sa.Integer(), nullable=True)

    op.create_index(
        "ix_activity_logs_created_at", "activity_logs", ["created_at"]
    )
    op.create_index(
        "ix_activity_logs_user_id_created_at",
        "activity_logs",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_activity_logs_entity",
        "activity_logs",
        ["entity_type", "entity_id"],
    )
    op.create_index(
        "ix_activity_logs_action", "activity_logs", ["action"]
    )


def downgrade() -> None:
    op.drop_index("ix_activity_logs_action", "activity_logs")
    op.drop_index("ix_activity_logs_entity", "activity_logs")
    op.drop_index("ix_activity_logs_user_id_created_at", "activity_logs")
    op.drop_index("ix_activity_logs_created_at", "activity_logs")
    op.alter_column(
        "activity_logs", "user_id", existing_type=sa.Integer(), nullable=False
    )
    op.drop_column("activity_logs", "ip_address")
    op.drop_column("activity_logs", "details")
    op.drop_column("activity_logs", "new_values")
    op.drop_column("activity_logs", "old_values")
    op.drop_column("activity_logs", "user_email")
