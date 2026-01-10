"""
Market data service for fetching stock quotes and historical data.

Uses Alpaca Market Data API for real-time and historical stock data.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import structlog
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest, StockQuotesRequest
from alpaca.data.timeframe import TimeFrame

from app.core.config import settings
from app.core.redis import get_redis_client

logger = structlog.get_logger()


class MarketDataService:
    """
    Market data service for fetching stock quotes and historical data.

    Supports caching via Redis to reduce API calls and improve performance.
    """

    def __init__(self):
        """Initialize Alpaca market data client."""
        if not settings.ALPACA_API_KEY or not settings.ALPACA_API_SECRET:
            logger.warning("alpaca_market_data_credentials_missing")
            self.client = None
        else:
            self.client = StockHistoricalDataClient(
                api_key=settings.ALPACA_API_KEY,
                secret_key=settings.ALPACA_API_SECRET
            )

        logger.info("market_data_service_initialized")

    async def get_latest_quote(self, symbol: str, use_cache: bool = True) -> Dict:
        """
        Get latest quote for a symbol.

        Args:
            symbol: Stock symbol
            use_cache: Whether to use Redis cache (default: True)

        Returns:
            Dict with quote data (bid, ask, last price, volume, timestamp)
        """
        cache_key = f"quote:{symbol}"

        # Try cache first
        if use_cache:
            try:
                redis = await get_redis_client()
                cached = await redis.get(cache_key)
                if cached:
                    import json
                    logger.debug("quote_cache_hit", symbol=symbol)
                    return json.loads(cached)
            except Exception as e:
                logger.warning("redis_cache_error", error=str(e))

        # Fetch from Alpaca
        try:
            request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
            quotes = self.client.get_stock_latest_quote(request)

            quote = quotes[symbol]

            result = {
                "symbol": symbol,
                "bid_price": float(quote.bid_price) if quote.bid_price else None,
                "ask_price": float(quote.ask_price) if quote.ask_price else None,
                "bid_size": int(quote.bid_size) if quote.bid_size else None,
                "ask_size": int(quote.ask_size) if quote.ask_size else None,
                "timestamp": quote.timestamp.isoformat() if quote.timestamp else None,
            }

            # Cache for 1 minute
            if use_cache:
                try:
                    redis = await get_redis_client()
                    import json
                    await redis.setex(cache_key, 60, json.dumps(result))
                except Exception as e:
                    logger.warning("redis_cache_set_error", error=str(e))

            logger.info("quote_fetched", symbol=symbol)
            return result

        except Exception as e:
            logger.error("get_latest_quote_failed", symbol=symbol, error=str(e))
            raise

    async def get_multiple_quotes(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        Get latest quotes for multiple symbols.

        Args:
            symbols: List of stock symbols

        Returns:
            Dict mapping symbol to quote data
        """
        try:
            request = StockLatestQuoteRequest(symbol_or_symbols=symbols)
            quotes = self.client.get_stock_latest_quote(request)

            result = {}
            for symbol in symbols:
                if symbol in quotes:
                    quote = quotes[symbol]
                    result[symbol] = {
                        "symbol": symbol,
                        "bid_price": float(quote.bid_price) if quote.bid_price else None,
                        "ask_price": float(quote.ask_price) if quote.ask_price else None,
                        "bid_size": int(quote.bid_size) if quote.bid_size else None,
                        "ask_size": int(quote.ask_size) if quote.ask_size else None,
                        "timestamp": quote.timestamp.isoformat() if quote.timestamp else None,
                    }

            logger.info("multiple_quotes_fetched", count=len(result))
            return result

        except Exception as e:
            logger.error("get_multiple_quotes_failed", symbols=symbols, error=str(e))
            raise

    async def get_historical_bars(
        self,
        symbol: str,
        timeframe: str = "1Day",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get historical OHLCV bars for a symbol.

        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe (1Min, 5Min, 15Min, 1Hour, 1Day)
            start: Start datetime (default: 100 days ago)
            end: End datetime (default: now)
            limit: Maximum number of bars to return

        Returns:
            List of OHLCV bar dicts
        """
        try:
            # Parse timeframe
            timeframe_map = {
                "1Min": TimeFrame.Minute,
                "5Min": TimeFrame(5, "Min"),
                "15Min": TimeFrame(15, "Min"),
                "1Hour": TimeFrame.Hour,
                "1Day": TimeFrame.Day,
            }

            tf = timeframe_map.get(timeframe, TimeFrame.Day)

            # Default date range
            if not end:
                end = datetime.utcnow()
            if not start:
                start = end - timedelta(days=100)

            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=tf,
                start=start,
                end=end,
                limit=limit
            )

            bars = self.client.get_stock_bars(request)

            result = []
            if symbol in bars:
                for bar in bars[symbol]:
                    result.append({
                        "timestamp": bar.timestamp.isoformat(),
                        "open": float(bar.open),
                        "high": float(bar.high),
                        "low": float(bar.low),
                        "close": float(bar.close),
                        "volume": int(bar.volume),
                        "vwap": float(bar.vwap) if hasattr(bar, 'vwap') and bar.vwap else None,
                    })

            logger.info(
                "historical_bars_fetched",
                symbol=symbol,
                timeframe=timeframe,
                count=len(result)
            )
            return result

        except Exception as e:
            logger.error(
                "get_historical_bars_failed",
                symbol=symbol,
                timeframe=timeframe,
                error=str(e)
            )
            raise

    async def get_market_status(self) -> Dict:
        """
        Get current market status (open/closed).

        Returns:
            Dict with market status information
        """
        try:
            clock = self.client.get_clock()

            return {
                "is_open": clock.is_open,
                "next_open": clock.next_open.isoformat() if clock.next_open else None,
                "next_close": clock.next_close.isoformat() if clock.next_close else None,
                "timestamp": clock.timestamp.isoformat() if clock.timestamp else None,
            }

        except Exception as e:
            logger.error("get_market_status_failed", error=str(e))
            # Return default if API fails
            return {
                "is_open": False,
                "next_open": None,
                "next_close": None,
                "timestamp": datetime.utcnow().isoformat(),
            }


# Global market data service instance
market_data_service = MarketDataService()
