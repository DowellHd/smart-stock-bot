"""
Alpaca broker service for paper and live trading.

Provides interface for placing orders, getting positions, and account data.
"""
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, List, Optional

import structlog
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide as AlpacaOrderSide, OrderType as AlpacaOrderType
from alpaca.trading.enums import TimeInForce
from alpaca.trading.requests import GetOrdersRequest, MarketOrderRequest, LimitOrderRequest
from alpaca.trading.models import Order as AlpacaOrder, Position as AlpacaPosition

from app.core.config import settings

logger = structlog.get_logger()


class BrokerInterface(ABC):
    """
    Abstract interface for broker implementations.

    Allows for multiple broker support (Alpaca, Interactive Brokers, etc.)
    """

    @abstractmethod
    async def get_account(self) -> Dict:
        """Get account information (cash, buying power, equity)."""
        pass

    @abstractmethod
    async def place_market_order(
        self,
        symbol: str,
        quantity: int,
        side: str,
        time_in_force: str = "gtc"
    ) -> Dict:
        """Place a market order."""
        pass

    @abstractmethod
    async def place_limit_order(
        self,
        symbol: str,
        quantity: int,
        side: str,
        limit_price: Decimal,
        time_in_force: str = "gtc"
    ) -> Dict:
        """Place a limit order."""
        pass

    @abstractmethod
    async def get_positions(self) -> List[Dict]:
        """Get all open positions."""
        pass

    @abstractmethod
    async def get_position(self, symbol: str) -> Optional[Dict]:
        """Get position for specific symbol."""
        pass

    @abstractmethod
    async def close_position(self, symbol: str) -> Dict:
        """Close position for symbol."""
        pass

    @abstractmethod
    async def get_orders(self, status: Optional[str] = None) -> List[Dict]:
        """Get orders, optionally filtered by status."""
        pass

    @abstractmethod
    async def get_order(self, order_id: str) -> Dict:
        """Get order by ID."""
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel pending order."""
        pass


class AlpacaBroker(BrokerInterface):
    """
    Alpaca broker implementation.

    Supports both paper and live trading modes.
    """

    def __init__(self, mode: str = "paper"):
        """
        Initialize Alpaca broker.

        Args:
            mode: Trading mode ('paper' or 'live')
        """
        self.mode = mode

        # Select appropriate API keys based on mode
        if mode == "live":
            api_key = settings.ALPACA_API_KEY
            secret_key = settings.ALPACA_API_SECRET
            paper = False
        else:
            # Paper trading uses same keys but with paper flag
            api_key = settings.ALPACA_API_KEY
            secret_key = settings.ALPACA_API_SECRET
            paper = True

        if not api_key or not secret_key:
            logger.warning("alpaca_credentials_missing", mode=mode)
            # Create client anyway for development, it will fail on actual API calls
            self.client = None
        else:
            self.client = TradingClient(
                api_key=api_key,
                secret_key=secret_key,
                paper=paper
            )

        logger.info("alpaca_broker_initialized", mode=mode, paper=paper)

    async def get_account(self) -> Dict:
        """Get Alpaca account information."""
        try:
            account = self.client.get_account()
            return {
                "cash": str(account.cash),
                "buying_power": str(account.buying_power),
                "equity": str(account.equity),
                "portfolio_value": str(account.portfolio_value),
                "currency": account.currency,
                "daytrade_count": account.daytrade_count,
                "pattern_day_trader": account.pattern_day_trader,
            }
        except Exception as e:
            logger.error("alpaca_get_account_failed", error=str(e), mode=self.mode)
            raise

    async def place_market_order(
        self,
        symbol: str,
        quantity: int,
        side: str,
        time_in_force: str = "gtc"
    ) -> Dict:
        """Place market order on Alpaca."""
        try:
            order_side = AlpacaOrderSide.BUY if side.lower() == "buy" else AlpacaOrderSide.SELL
            tif = TimeInForce[time_in_force.upper()]

            market_order_data = MarketOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=order_side,
                time_in_force=tif
            )

            order = self.client.submit_order(order_data=market_order_data)

            logger.info(
                "alpaca_market_order_placed",
                order_id=order.id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                mode=self.mode
            )

            return self._serialize_order(order)

        except Exception as e:
            logger.error(
                "alpaca_place_order_failed",
                error=str(e),
                symbol=symbol,
                side=side,
                mode=self.mode
            )
            raise

    async def place_limit_order(
        self,
        symbol: str,
        quantity: int,
        side: str,
        limit_price: Decimal,
        time_in_force: str = "gtc"
    ) -> Dict:
        """Place limit order on Alpaca."""
        try:
            order_side = AlpacaOrderSide.BUY if side.lower() == "buy" else AlpacaOrderSide.SELL
            tif = TimeInForce[time_in_force.upper()]

            limit_order_data = LimitOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=order_side,
                time_in_force=tif,
                limit_price=float(limit_price)
            )

            order = self.client.submit_order(order_data=limit_order_data)

            logger.info(
                "alpaca_limit_order_placed",
                order_id=order.id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                limit_price=str(limit_price),
                mode=self.mode
            )

            return self._serialize_order(order)

        except Exception as e:
            logger.error(
                "alpaca_place_limit_order_failed",
                error=str(e),
                symbol=symbol,
                side=side,
                mode=self.mode
            )
            raise

    async def get_positions(self) -> List[Dict]:
        """Get all positions from Alpaca."""
        try:
            positions = self.client.get_all_positions()
            return [self._serialize_position(p) for p in positions]
        except Exception as e:
            logger.error("alpaca_get_positions_failed", error=str(e), mode=self.mode)
            raise

    async def get_position(self, symbol: str) -> Optional[Dict]:
        """Get position for specific symbol."""
        try:
            position = self.client.get_open_position(symbol)
            return self._serialize_position(position)
        except Exception as e:
            if "position does not exist" in str(e).lower():
                return None
            logger.error("alpaca_get_position_failed", error=str(e), symbol=symbol, mode=self.mode)
            raise

    async def close_position(self, symbol: str) -> Dict:
        """Close position for symbol."""
        try:
            order = self.client.close_position(symbol)
            logger.info("alpaca_position_closed", symbol=symbol, mode=self.mode)
            return self._serialize_order(order)
        except Exception as e:
            logger.error("alpaca_close_position_failed", error=str(e), symbol=symbol, mode=self.mode)
            raise

    async def get_orders(self, status: Optional[str] = None) -> List[Dict]:
        """Get orders from Alpaca."""
        try:
            request = GetOrdersRequest(status=status) if status else GetOrdersRequest()
            orders = self.client.get_orders(filter=request)
            return [self._serialize_order(o) for o in orders]
        except Exception as e:
            logger.error("alpaca_get_orders_failed", error=str(e), mode=self.mode)
            raise

    async def get_order(self, order_id: str) -> Dict:
        """Get order by ID."""
        try:
            order = self.client.get_order_by_id(order_id)
            return self._serialize_order(order)
        except Exception as e:
            logger.error("alpaca_get_order_failed", error=str(e), order_id=order_id, mode=self.mode)
            raise

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel order."""
        try:
            self.client.cancel_order_by_id(order_id)
            logger.info("alpaca_order_canceled", order_id=order_id, mode=self.mode)
            return True
        except Exception as e:
            logger.error("alpaca_cancel_order_failed", error=str(e), order_id=order_id, mode=self.mode)
            return False

    def _serialize_order(self, order: AlpacaOrder) -> Dict:
        """Serialize Alpaca order to dict."""
        return {
            "id": order.id,
            "symbol": order.symbol,
            "side": order.side.value,
            "quantity": int(order.qty),
            "order_type": order.type.value,
            "status": order.status.value,
            "filled_quantity": int(order.filled_qty) if order.filled_qty else 0,
            "filled_avg_price": str(order.filled_avg_price) if order.filled_avg_price else None,
            "limit_price": str(order.limit_price) if order.limit_price else None,
            "stop_price": str(order.stop_price) if order.stop_price else None,
            "time_in_force": order.time_in_force.value,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "updated_at": order.updated_at.isoformat() if order.updated_at else None,
            "filled_at": order.filled_at.isoformat() if order.filled_at else None,
        }

    def _serialize_position(self, position: AlpacaPosition) -> Dict:
        """Serialize Alpaca position to dict."""
        return {
            "symbol": position.symbol,
            "quantity": int(position.qty),
            "avg_entry_price": str(position.avg_entry_price),
            "current_price": str(position.current_price),
            "market_value": str(position.market_value),
            "cost_basis": str(position.cost_basis),
            "unrealized_pl": str(position.unrealized_pl),
            "unrealized_pl_percent": str(position.unrealized_plpc),
            "side": position.side.value if hasattr(position, 'side') else None,
        }


def get_broker(mode: str = "paper") -> BrokerInterface:
    """
    Get broker instance based on mode.

    Args:
        mode: Trading mode ('paper' or 'live')

    Returns:
        BrokerInterface implementation

    Raises:
        ValueError: If mode is invalid or live trading is disabled
    """
    if mode not in ["paper", "live"]:
        raise ValueError(f"Invalid trading mode: {mode}. Must be 'paper' or 'live'.")

    if mode == "live" and not settings.ENABLE_LIVE_TRADING:
        raise ValueError("Live trading is disabled. Set ENABLE_LIVE_TRADING=true in .env")

    return AlpacaBroker(mode=mode)
