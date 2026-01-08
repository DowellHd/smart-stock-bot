"""
Trading models for orders, positions, and account snapshots.
"""
import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ENUM as PGENUM, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TradingMode(str, enum.Enum):
    """Trading mode enum."""

    PAPER = "paper"
    LIVE = "live"


class OrderSide(str, enum.Enum):
    """Order side enum."""

    BUY = "buy"
    SELL = "sell"


class OrderType(str, enum.Enum):
    """Order type enum."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(str, enum.Enum):
    """Order status enum."""

    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELED = "canceled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class Order(Base):
    """
    Order model for tracking trade orders.

    Supports both paper and live trading modes.
    """

    __tablename__ = "orders"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    mode: Mapped[TradingMode] = mapped_column(
        PGENUM('paper', 'live', name='trading_mode', create_type=False), nullable=False, index=True
    )
    symbol: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    side: Mapped[OrderSide] = mapped_column(
        PGENUM('buy', 'sell', name='order_side', create_type=False), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    order_type: Mapped[OrderType] = mapped_column(
        PGENUM('market', 'limit', 'stop', 'stop_limit', name='order_type', create_type=False), nullable=False
    )
    limit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    stop_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[OrderStatus] = mapped_column(
        PGENUM('pending', 'filled', 'partially_filled', 'canceled', 'rejected', 'expired', name='order_status', create_type=False),
        nullable=False,
        index=True
    )
    filled_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filled_avg_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    broker_order_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True, index=True)
    broker_name: Mapped[str] = mapped_column(String(50), nullable=False, default="alpaca")
    time_in_force: Mapped[str] = mapped_column(String(10), nullable=False, default="gtc")
    extended_hours: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    filled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Order(id={self.id}, symbol={self.symbol}, side={self.side}, status={self.status})>"


class Position(Base):
    """
    Position model for tracking open positions.

    Represents current holdings in a user's portfolio.
    """

    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint('user_id', 'mode', 'symbol', 'broker_name', name='uq_positions_user_mode_symbol_broker'),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    mode: Mapped[TradingMode] = mapped_column(
        PGENUM('paper', 'live', name='trading_mode', create_type=False), nullable=False, index=True
    )
    symbol: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_entry_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    current_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    market_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    cost_basis: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unrealized_pl: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unrealized_pl_percent: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    broker_name: Mapped[str] = mapped_column(String(50), nullable=False, default="alpaca")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<Position(symbol={self.symbol}, quantity={self.quantity}, unrealized_pl={self.unrealized_pl})>"


class AccountSnapshot(Base):
    """
    Account snapshot model for tracking portfolio value over time.

    Used for performance charts and historical analysis.
    """

    __tablename__ = "account_snapshots"
    __table_args__ = (
        UniqueConstraint('user_id', 'mode', 'snapshot_date', name='uq_account_snapshots_user_mode_date'),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    mode: Mapped[TradingMode] = mapped_column(
        PGENUM('paper', 'live', name='trading_mode', create_type=False), nullable=False, index=True
    )
    equity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    cash: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    buying_power: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    portfolio_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    snapshot_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<AccountSnapshot(date={self.snapshot_date}, value={self.portfolio_value})>"
