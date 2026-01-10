"""
Trading signal generation service.

Implements baseline strategies for generating buy/sell signals.
Initial implementation uses Simple Moving Average (SMA) crossover strategy.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

import structlog

from app.services.market_data import market_data_service

logger = structlog.get_logger()


class SignalService:
    """
    Trading signal generation service.

    Generates buy/sell signals using technical analysis strategies.
    """

    def __init__(self):
        """Initialize signal service."""
        self.market_data = market_data_service
        logger.info("signal_service_initialized")

    async def generate_signal(
        self,
        symbol: str,
        strategy: str = "sma_crossover",
        user_plan: str = "free"
    ) -> Dict:
        """
        Generate trading signal for a symbol.

        Args:
            symbol: Stock symbol
            strategy: Strategy to use (default: sma_crossover)
            user_plan: User's subscription plan (for signal delay)

        Returns:
            Dict with signal data (action, confidence, reasoning, available_at)
        """
        try:
            if strategy == "sma_crossover":
                signal = await self._sma_crossover_strategy(symbol)
            else:
                raise ValueError(f"Unknown strategy: {strategy}")

            # Apply signal delay based on user plan
            signal_delay_minutes = self._get_signal_delay(user_plan)
            signal["available_at"] = (
                datetime.utcnow() + timedelta(minutes=signal_delay_minutes)
            ).isoformat()
            signal["delayed"] = signal_delay_minutes > 0
            signal["delay_minutes"] = signal_delay_minutes

            logger.info(
                "signal_generated",
                symbol=symbol,
                action=signal["action"],
                plan=user_plan,
                delay_minutes=signal_delay_minutes
            )

            return signal

        except Exception as e:
            logger.error(
                "generate_signal_failed",
                symbol=symbol,
                strategy=strategy,
                error=str(e),
                exc_info=True
            )
            raise

    async def _sma_crossover_strategy(self, symbol: str) -> Dict:
        """
        Simple Moving Average Crossover Strategy.

        Rules:
        - Buy when 50-day SMA crosses above 200-day SMA (golden cross)
        - Sell when 50-day SMA crosses below 200-day SMA (death cross)
        - Hold otherwise

        Args:
            symbol: Stock symbol

        Returns:
            Dict with signal action, confidence, and reasoning
        """
        # Fetch historical data (need 200 days + buffer)
        bars = await self.market_data.get_historical_bars(
            symbol=symbol,
            timeframe="1Day",
            limit=250
        )

        if len(bars) < 200:
            return {
                "symbol": symbol,
                "action": "hold",
                "confidence": 0.0,
                "reason": f"Insufficient data for analysis (need 200 bars, got {len(bars)})",
                "strategy": "sma_crossover",
                "current_price": None,
                "sma_50": None,
                "sma_200": None,
                "timestamp": datetime.utcnow().isoformat(),
            }

        # Calculate SMAs
        closes = [bar["close"] for bar in bars]
        sma_50 = sum(closes[-50:]) / 50
        sma_200 = sum(closes[-200:]) / 200

        # Get previous SMAs to detect crossover
        prev_sma_50 = sum(closes[-51:-1]) / 50
        prev_sma_200 = sum(closes[-201:-1]) / 200

        current_price = closes[-1]

        # Determine signal
        action = "hold"
        confidence = 0.5
        reason = "No clear signal"

        # Golden cross: 50-day crosses above 200-day
        if prev_sma_50 <= prev_sma_200 and sma_50 > sma_200:
            action = "buy"
            confidence = 0.75
            reason = f"Golden cross detected: 50-day SMA (${sma_50:.2f}) crossed above 200-day SMA (${sma_200:.2f})"

        # Death cross: 50-day crosses below 200-day
        elif prev_sma_50 >= prev_sma_200 and sma_50 < sma_200:
            action = "sell"
            confidence = 0.75
            reason = f"Death cross detected: 50-day SMA (${sma_50:.2f}) crossed below 200-day SMA (${sma_200:.2f})"

        # Existing uptrend
        elif sma_50 > sma_200:
            action = "hold"
            confidence = 0.65
            reason = f"Uptrend continues: 50-day SMA (${sma_50:.2f}) above 200-day SMA (${sma_200:.2f})"

        # Existing downtrend
        elif sma_50 < sma_200:
            action = "hold"
            confidence = 0.60
            reason = f"Downtrend continues: 50-day SMA (${sma_50:.2f}) below 200-day SMA (${sma_200:.2f})"

        return {
            "symbol": symbol,
            "action": action,
            "confidence": confidence,
            "reason": reason,
            "strategy": "sma_crossover",
            "current_price": current_price,
            "sma_50": round(sma_50, 2),
            "sma_200": round(sma_200, 2),
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def generate_bulk_signals(
        self,
        symbols: List[str],
        strategy: str = "sma_crossover",
        user_plan: str = "free"
    ) -> List[Dict]:
        """
        Generate signals for multiple symbols.

        Args:
            symbols: List of stock symbols
            strategy: Strategy to use
            user_plan: User's subscription plan

        Returns:
            List of signal dicts
        """
        signals = []

        for symbol in symbols:
            try:
                signal = await self.generate_signal(symbol, strategy, user_plan)
                signals.append(signal)
            except Exception as e:
                logger.error(
                    "bulk_signal_generation_failed",
                    symbol=symbol,
                    error=str(e)
                )
                # Add error signal
                signals.append({
                    "symbol": symbol,
                    "action": "error",
                    "confidence": 0.0,
                    "reason": f"Failed to generate signal: {str(e)}",
                    "strategy": strategy,
                    "timestamp": datetime.utcnow().isoformat(),
                })

        return signals

    def _get_signal_delay(self, user_plan: str) -> int:
        """
        Get signal delay in minutes based on user plan.

        Args:
            user_plan: User's subscription plan (free, starter, pro)

        Returns:
            Delay in minutes
        """
        delay_map = {
            "free": 15,      # 15-minute delay
            "starter": 0,    # Real-time
            "pro": 0,        # Real-time
        }

        return delay_map.get(user_plan.lower(), 15)


# Global signal service instance
signal_service = SignalService()
