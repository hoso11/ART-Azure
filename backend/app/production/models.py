import enum
from datetime import datetime
from sqlalchemy import (
    String, Integer, Boolean, ForeignKey, DateTime, Text, Enum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class StageName(str, enum.Enum):
    cutting = "cutting"
    sewing = "sewing"
    quality_control = "quality_control"
    packaging = "packaging"
    ready_for_shipment = "ready_for_shipment"


class StageStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"


# Valid stage / status values for stock-based ProductionBatch.
# Strings (not enums) so the batch workflow can evolve without DB migrations.
VALID_BATCH_STAGES = {
    "cutting", "processing", "quality_control",
    "packaging", "warehousing", "ready_for_shipment",
}
VALID_BATCH_STATUSES = {"pending", "in_progress", "completed"}


class ProductionStage(Base):
    __tablename__ = "production_stages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False)
    stage_name: Mapped[StageName] = mapped_column(Enum(StageName), nullable=False)
    status: Mapped[StageStatus] = mapped_column(
        Enum(StageStatus), nullable=False, default=StageStatus.pending
    )
    assigned_to: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    order = relationship("Order", back_populates="production_stages", lazy="selectin")
    assignee = relationship("User", lazy="selectin")
    logs = relationship(
        "ProductionLog", back_populates="stage", lazy="selectin",
        cascade="all, delete-orphan",
    )


class ProductionLog(Base):
    __tablename__ = "production_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    production_stage_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("production_stages.id"), nullable=False
    )
    changed_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    previous_status: Mapped[StageStatus] = mapped_column(Enum(StageStatus), nullable=False)
    new_status: Mapped[StageStatus] = mapped_column(Enum(StageStatus), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    stage = relationship("ProductionStage", back_populates="logs")
    user = relationship("User", lazy="selectin")


class ProductionBatch(Base):
    """Stock-based production batch — finished-goods replenishment, no order link.
    Materials are deducted at creation; finished stock is added on completion.
    """
    __tablename__ = "production_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    # Nullable since migration 015_variant_force_delete. Set to NULL by
    # the admin variant force-delete flow, which snapshots the variant's
    # "size / color" and the parent product's name into the *_snapshot
    # columns before NULLing this column. Production history (good /
    # damaged counts, stage progression, stock_movements via batch_id)
    # otherwise stays intact for reports.
    variant_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("product_variants.id"), nullable=True)
    variant_name_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product_name_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity_to_produce: Mapped[int] = mapped_column(Integer, nullable=False)
    production_type: Mapped[str] = mapped_column(String(20), nullable=False, default="stock_based")
    current_stage: Mapped[str] = mapped_column(String(50), nullable=False, default="cutting")
    stage_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    materials_deducted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    stock_added: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    good_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    damaged_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    defect_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    product = relationship("Product", lazy="selectin")
    variant = relationship("ProductVariant", lazy="selectin")
    creator = relationship("User", lazy="selectin")
