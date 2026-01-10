"""
Market data API endpoints for quotes, historical data, and market status.
"""
from datetime import datetime, timedelta
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.market_data import (
    QuoteResponse,
    HistoricalBarsResponse,
    OHLCVBar,
    MarketStatusResponse,
)
from app.services.market_data import market_data_service

logger = structlog.get_logger()

router = APIRouter()


@router.get("/quote/{symbol}", response_model=QuoteResponse)
async def get_quote(
    symbol: str,
    use_cache: bool = True,
    current_user: User = Depends(get_current_user),
):
    """
    Get latest quote for a symbol.

    **Parameters:**
    - symbol: Stock symbol (e.g., AAPL, GOOGL)
    - use_cache: Whether to use Redis cache (default: True)

    **Returns:**
    Quote data with bid/ask prices and timestamp.
    """
    try:
        quote = await market_data_service.get_latest_quote(symbol.upper(), use_cache=use_cache)
        return QuoteResponse(**quote)

    except Exception as e:
        logger.error(
            "get_quote_failed",
            user_id=str(current_user.id),
            symbol=symbol,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch quote for {symbol}",
        )


@router.get("/quotes", response_model=List[QuoteResponse])
async def get_multiple_quotes(
    symbols: List[str] = Query(..., description="List of stock symbols"),
    current_user: User = Depends(get_current_user),
):
    """
    Get latest quotes for multiple symbols.

    **Parameters:**
    - symbols: List of stock symbols (e.g., ["AAPL", "GOOGL", "MSFT"])

    **Returns:**
    List of quote data for requested symbols.
    """
    try:
        # Limit to 50 symbols per request
        if len(symbols) > 50:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 50 symbols allowed per request",
            )

        symbols_upper = [s.upper() for s in symbols]
        quotes_dict = await market_data_service.get_multiple_quotes(symbols_upper)

        # Convert dict to list
        quotes = [QuoteResponse(**quote) for quote in quotes_dict.values()]

        return quotes

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_multiple_quotes_failed",
            user_id=str(current_user.id),
            symbols=symbols,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch quotes",
        )


@router.get("/bars/{symbol}", response_model=HistoricalBarsResponse)
async def get_historical_bars(
    symbol: str,
    timeframe: str = Query("1Day", pattern="^(1Min|5Min|15Min|1Hour|1Day)$"),
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
):
    """
    Get historical OHLCV bars for a symbol.

    **Parameters:**
    - symbol: Stock symbol (e.g., AAPL)
    - timeframe: Bar timeframe (1Min, 5Min, 15Min, 1Hour, 1Day)
    - start: Start datetime (ISO format, optional)
    - end: End datetime (ISO format, optional)
    - limit: Maximum number of bars (1-1000, default 100)

    **Returns:**
    Historical OHLCV bar data.
    """
    try:
        # Parse datetimes
        start_dt = datetime.fromisoformat(start) if start else None
        end_dt = datetime.fromisoformat(end) if end else None

        bars = await market_data_service.get_historical_bars(
            symbol=symbol.upper(),
            timeframe=timeframe,
            start=start_dt,
            end=end_dt,
            limit=limit,
        )

        # Convert to response schema
        ohlcv_bars = [OHLCVBar(**bar) for bar in bars]

        return HistoricalBarsResponse(
            symbol=symbol.upper(),
            timeframe=timeframe,
            bars=ohlcv_bars,
            count=len(ohlcv_bars),
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid datetime format: {str(e)}",
        )
    except Exception as e:
        logger.error(
            "get_historical_bars_failed",
            user_id=str(current_user.id),
            symbol=symbol,
            timeframe=timeframe,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch historical bars for {symbol}",
        )


@router.get("/status", response_model=MarketStatusResponse)
async def get_market_status(
    current_user: User = Depends(get_current_user),
):
    """
    Get current market status (open/closed).

    **Returns:**
    Market status with next open/close times.
    """
    try:
        status_data = await market_data_service.get_market_status()
        return MarketStatusResponse(**status_data)

    except Exception as e:
        logger.error(
            "get_market_status_failed",
            user_id=str(current_user.id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch market status",
        )
