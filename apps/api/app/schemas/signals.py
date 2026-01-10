"""
Trading signal schemas for API requests and responses.
"""
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


class GenerateSignalRequest(BaseModel):
    """Request schema for generating a signal."""

    symbol: str = Field(..., min_length=1, max_length=10, description="Stock symbol")
    strategy: str = Field(
        default="sma_crossover",
        pattern="^(sma_crossover)$",
        description="Strategy to use"
    )


class SignalResponse(BaseModel):
    """Response schema for trading signal."""

    symbol: str = Field(..., description="Stock symbol")
    action: str = Field(..., description="Signal action: buy, sell, or hold")
    confidence: float = Field(..., ge=0, le=1, description="Confidence score (0-1)")
    reason: str = Field(..., description="Human-readable explanation")
    strategy: str = Field(..., description="Strategy used")
    current_price: Optional[Decimal] = Field(None, description="Current price")
    sma_50: Optional[float] = Field(None, description="50-day simple moving average")
    sma_200: Optional[float] = Field(None, description="200-day simple moving average")
    timestamp: str = Field(..., description="Signal generation timestamp")
    available_at: str = Field(..., description="When signal becomes available (delayed for free users)")
    delayed: bool = Field(..., description="Whether signal is delayed")
    delay_minutes: int = Field(..., description="Delay in minutes")


class BulkSignalRequest(BaseModel):
    """Request schema for generating signals for multiple symbols."""

    symbols: List[str] = Field(..., min_length=1, max_length=20, description="List of stock symbols")
    strategy: str = Field(
        default="sma_crossover",
        pattern="^(sma_crossover)$",
        description="Strategy to use"
    )


class BulkSignalResponse(BaseModel):
    """Response schema for bulk signals."""

    signals: List[SignalResponse]
    total: int
