import enum
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Integer, ForeignKey, DateTime, Text, Numeric, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class StockMovementReason(str, enum.Enum):
    purchase = "purchase"
    production_usage = "production_usage"
    adjustment = "adjustment"
    return_ = "return"


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    low_stock_threshold: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    inventory = relationship("Inventory", back_populates="material", uselist=False, lazy="selectin")


class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    material_id: Mapped[int] = mapped_column(Integer, ForeignKey("materials.id"), unique=True, nullable=False)
    quantity_on_hand: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=0)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    material = relationship("Material", back_populates="inventory")


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    material_id: Mapped[int] = mapped_column(Integer, ForeignKey("materials.id"), nullable=False)
    order_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("orders.id"), nullable=True)
    quantity_change: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    reason: Mapped[StockMovementReason] = mapped_column(Enum(StockMovementReason), nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    material = relationship("Material", lazy="selectin")
    order = relationship("Order", lazy="selectin")
