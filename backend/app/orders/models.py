import enum
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Boolean, Integer, ForeignKey, DateTime, Text, Numeric, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class OrderStatus(str, enum.Enum):
    draft = "draft"
    confirmed = "confirmed"
    in_production = "in_production"
    completed = "completed"
    shipped = "shipped"
    cancelled = "cancelled"


class OrderPriority(str, enum.Enum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.draft)
    priority: Mapped[OrderPriority] = mapped_column(Enum(OrderPriority), default=OrderPriority.normal)
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    materials_deducted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    stock_deducted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = relationship("Customer", back_populates="orders", lazy="selectin")
    creator = relationship("User", lazy="selectin")
    items = relationship("OrderItem", back_populates="order", lazy="selectin", cascade="all, delete-orphan")
    production_stages = relationship("ProductionStage", back_populates="order", lazy="noload")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False)
    product_variant_id: Mapped[int] = mapped_column(Integer, ForeignKey("product_variants.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    fulfilled_from_stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    production_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    order = relationship("Order", back_populates="items")
    product_variant = relationship("ProductVariant", lazy="selectin")
