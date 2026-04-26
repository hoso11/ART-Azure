import enum
from datetime import datetime
from sqlalchemy import String, Integer, ForeignKey, DateTime, Text, Enum
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
    skipped = "skipped"


class ProductionStage(Base):
    __tablename__ = "production_stages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False)
    stage_name: Mapped[StageName] = mapped_column(Enum(StageName), nullable=False)
    status: Mapped[StageStatus] = mapped_column(Enum(StageStatus), default=StageStatus.pending)
    assigned_to: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    order = relationship("Order", back_populates="production_stages", lazy="selectin")
    assignee = relationship("User", lazy="selectin")
    logs = relationship("ProductionLog", back_populates="stage", lazy="selectin", cascade="all, delete-orphan")


class ProductionLog(Base):
    __tablename__ = "production_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    production_stage_id: Mapped[int] = mapped_column(Integer, ForeignKey("production_stages.id"), nullable=False)
    changed_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    previous_status: Mapped[str] = mapped_column(String(50), nullable=False)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    stage = relationship("ProductionStage", back_populates="logs")
    user = relationship("User", lazy="selectin")
