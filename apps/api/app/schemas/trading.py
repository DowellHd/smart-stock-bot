"""
Trading schemas for API requests and responses.
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class PlaceOrderRequest(BaseModel):
    """Request schema for placing an order."""

    symbol: str = Field(..., min_length=1, max_length=10, description="Stock symbol")
    quantity: int = Field(..., gt=0, description="Number of shares")
    side: str = Field(..., pattern="^(buy|sell)$", description="Order side: buy or sell")
    order_type: str = Field(
        default="market",
        pattern="^(market|limit|stop|stop_limit)$",
        description="Order type"
    )
    limit_price: Optional[Decimal] = Field(None, gt=0, description="Limit price (required for limit orders)")
    stop_price: Optional[Decimal] = Field(None, gt=0, description="Stop price (required for stop orders)")
    time_in_force: str = Field(
        default="gtc",
        pattern="^(gtc|day|ioc|fok)$",
        description="Time in force"
    )
    mode: str = Field(
        default="paper",
        pattern="^(paper|live)$",
        description="Trading mode"
    )

    @field_validator("symbol")
    @classmethod
    def symbol_uppercase(cls, v: str) -> str:
        """Convert symbol to uppercase."""
        return v.upper()

    @field_validator("side", "order_type", "time_in_force", "mode")
    @classmethod
    def lowercase_fields(cls, v: str) -> str:
        """Convert fields to lowercase."""
        return v.lower()


class OrderResponse(BaseModel):
    """Response schema for order data."""

    id: UUID
    user_id: UUID
    mode: str
    symbol: str
    side: str
    quantity: int
    order_type: str
    limit_price: Optional[Decimal]
    stop_price: Optional[Decimal]
    status: str
    filled_quantity: int
    filled_avg_price: Optional[Decimal]
    broker_order_id: Optional[str]
    broker_name: str
    time_in_force: str
    extended_hours: bool
    created_at: datetime
    updated_at: datetime
    filled_at: Optional[datetime]

    class Config:
        from_attributes = True


class PositionResponse(BaseModel):
    """Response schema for position data."""

    id: UUID
    user_id: UUID
    mode: str
    symbol: str
    quantity: int
    avg_entry_price: Decimal
    current_price: Decimal
    market_value: Decimal
    cost_basis: Decimal
    unrealized_pl: Decimal
    unrealized_pl_percent: Decimal
    broker_name: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AccountResponse(BaseModel):
    """Response schema for account data."""

    cash: Decimal = Field(..., description="Available cash")
    buying_power: Decimal = Field(..., description="Buying power")
    equity: Decimal = Field(..., description="Total equity")
    portfolio_value: Decimal = Field(..., description="Total portfolio value")
    currency: str = Field(default="USD", description="Account currency")
    daytrade_count: Optional[int] = Field(None, description="Number of day trades in the last 5 days")
    pattern_day_trader: bool = Field(default=False, description="Pattern day trader status")


class AccountSnapshotResponse(BaseModel):
    """Response schema for account snapshot."""

    id: UUID
    user_id: UUID
    mode: str
    equity: Decimal
    cash: Decimal
    buying_power: Decimal
    portfolio_value: Decimal
    snapshot_date: str  # Date as string
    snapshot_time: datetime

    class Config:
        from_attributes = True


class PortfolioSummary(BaseModel):
    """Portfolio summary with positions and account data."""

    account: AccountResponse
    positions: List[PositionResponse]
    total_positions: int
    total_market_value: Decimal
    total_unrealized_pl: Decimal
    total_unrealized_pl_percent: Decimal


class CancelOrderResponse(BaseModel):
    """Response schema for cancel order."""

    success: bool
    message: str
    order_id: UUID
