"""
Market data schemas for API requests and responses.
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


class QuoteResponse(BaseModel):
    """Response schema for stock quote."""

    symbol: str = Field(..., description="Stock symbol")
    bid_price: Optional[Decimal] = Field(None, description="Bid price")
    ask_price: Optional[Decimal] = Field(None, description="Ask price")
    bid_size: Optional[int] = Field(None, description="Bid size")
    ask_size: Optional[int] = Field(None, description="Ask size")
    timestamp: Optional[str] = Field(None, description="Quote timestamp")


class OHLCVBar(BaseModel):
    """OHLCV bar data."""

    timestamp: str = Field(..., description="Bar timestamp")
    open: Decimal = Field(..., description="Open price")
    high: Decimal = Field(..., description="High price")
    low: Decimal = Field(..., description="Low price")
    close: Decimal = Field(..., description="Close price")
    volume: int = Field(..., description="Volume")
    vwap: Optional[Decimal] = Field(None, description="Volume-weighted average price")


class HistoricalBarsResponse(BaseModel):
    """Response schema for historical bars."""

    symbol: str
    timeframe: str
    bars: List[OHLCVBar]
    count: int


class MarketStatusResponse(BaseModel):
    """Response schema for market status."""

    is_open: bool = Field(..., description="Whether market is currently open")
    next_open: Optional[str] = Field(None, description="Next market open time")
    next_close: Optional[str] = Field(None, description="Next market close time")
    timestamp: Optional[str] = Field(None, description="Current timestamp")
