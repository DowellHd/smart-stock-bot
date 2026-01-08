"""
Trading API endpoints for placing orders, managing positions, and viewing account data.
"""
from decimal import Decimal
from typing import List
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.entitlements import get_entitlements, Entitlements
from app.models.trading import Order, Position, OrderStatus, TradingMode
from app.models.user import User
from app.schemas.trading import (
    PlaceOrderRequest,
    OrderResponse,
    PositionResponse,
    AccountResponse,
    PortfolioSummary,
    CancelOrderResponse,
)
from app.services.alpaca import get_broker

logger = structlog.get_logger()

router = APIRouter()


# ============================================================================
# Orders
# ============================================================================


@router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def place_order(
    order_request: PlaceOrderRequest,
    current_user: User = Depends(get_current_user),
    entitlements: Entitlements = Depends(get_entitlements),
    db: AsyncSession = Depends(get_db),
):
    """
    Place a trading order (market or limit).

    Supports both paper and live trading modes.

    **Requirements:**
    - **Paper trading**: All users
    - **Live trading**: Pro plan only + admin approval required
    """
    try:
        # Check if live trading is allowed
        if order_request.mode == "live":
            entitlements.require_feature("live_trading_enabled", True)

            # Additional check: user must be approved for live trading
            if not current_user.live_trading_approved:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Live trading requires admin approval. Contact support to enable.",
                )

        # Get broker instance
        broker = get_broker(mode=order_request.mode)

        # Place order with broker
        if order_request.order_type == "market":
            broker_order = await broker.place_market_order(
                symbol=order_request.symbol,
                quantity=order_request.quantity,
                side=order_request.side,
                time_in_force=order_request.time_in_force,
            )
        elif order_request.order_type == "limit":
            if not order_request.limit_price:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Limit price required for limit orders",
                )
            broker_order = await broker.place_limit_order(
                symbol=order_request.symbol,
                quantity=order_request.quantity,
                side=order_request.side,
                limit_price=order_request.limit_price,
                time_in_force=order_request.time_in_force,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Order type '{order_request.order_type}' not yet supported",
            )

        # Save order to database
        db_order = Order(
            user_id=current_user.id,
            mode=TradingMode(order_request.mode),
            symbol=order_request.symbol,
            side=order_request.side,
            quantity=order_request.quantity,
            order_type=order_request.order_type,
            limit_price=order_request.limit_price,
            stop_price=order_request.stop_price,
            status=OrderStatus(broker_order["status"]),
            filled_quantity=broker_order.get("filled_quantity", 0),
            filled_avg_price=Decimal(broker_order["filled_avg_price"]) if broker_order.get("filled_avg_price") else None,
            broker_order_id=broker_order["id"],
            broker_name="alpaca",
            time_in_force=order_request.time_in_force,
            extended_hours=False,
        )

        db.add(db_order)
        await db.commit()
        await db.refresh(db_order)

        logger.info(
            "order_placed",
            user_id=str(current_user.id),
            order_id=str(db_order.id),
            symbol=order_request.symbol,
            side=order_request.side,
            mode=order_request.mode,
        )

        return db_order

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "place_order_failed",
            user_id=str(current_user.id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to place order: {str(e)}",
        )


@router.get("/orders", response_model=List[OrderResponse])
async def list_orders(
    mode: str = "paper",
    status_filter: str = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List user's trading orders.

    Query parameters:
    - mode: Trading mode (paper or live)
    - status_filter: Filter by order status
    - limit: Maximum number of orders to return
    """
    try:
        query = select(Order).where(
            Order.user_id == current_user.id,
            Order.mode == mode
        )

        if status_filter:
            query = query.where(Order.status == status_filter)

        query = query.order_by(Order.created_at.desc()).limit(limit)

        result = await db.execute(query)
        orders = result.scalars().all()

        return orders

    except Exception as e:
        logger.error(
            "list_orders_failed",
            user_id=str(current_user.id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve orders",
        )


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get order by ID."""
    try:
        result = await db.execute(
            select(Order).where(
                Order.id == order_id,
                Order.user_id == current_user.id
            )
        )
        order = result.scalar_one_or_none()

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )

        return order

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_order_failed",
            user_id=str(current_user.id),
            order_id=str(order_id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve order",
        )


@router.delete("/orders/{order_id}", response_model=CancelOrderResponse)
async def cancel_order(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a pending order."""
    try:
        # Get order from database
        result = await db.execute(
            select(Order).where(
                Order.id == order_id,
                Order.user_id == current_user.id
            )
        )
        order = result.scalar_one_or_none()

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )

        if order.status not in [OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED]:
            return CancelOrderResponse(
                success=False,
                message=f"Order cannot be canceled (status: {order.status.value})",
                order_id=order_id,
            )

        # Cancel with broker
        broker = get_broker(mode=order.mode.value)
        success = await broker.cancel_order(order.broker_order_id)

        if success:
            order.status = OrderStatus.CANCELED
            await db.commit()

            logger.info(
                "order_canceled",
                user_id=str(current_user.id),
                order_id=str(order_id),
            )

        return CancelOrderResponse(
            success=success,
            message="Order canceled successfully" if success else "Failed to cancel order",
            order_id=order_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "cancel_order_failed",
            user_id=str(current_user.id),
            order_id=str(order_id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel order",
        )


# ============================================================================
# Positions
# ============================================================================


@router.get("/positions", response_model=List[PositionResponse])
async def list_positions(
    mode: str = "paper",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List user's open positions.

    Query parameters:
    - mode: Trading mode (paper or live)
    """
    try:
        result = await db.execute(
            select(Position).where(
                Position.user_id == current_user.id,
                Position.mode == mode
            )
        )
        positions = result.scalars().all()

        return positions

    except Exception as e:
        logger.error(
            "list_positions_failed",
            user_id=str(current_user.id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve positions",
        )


@router.post("/positions/sync")
async def sync_positions(
    mode: str = "paper",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Sync positions from broker to local database.

    Useful after placing orders to update position data.
    """
    try:
        broker = get_broker(mode=mode)
        broker_positions = await broker.get_positions()

        logger.info(
            "syncing_positions",
            user_id=str(current_user.id),
            mode=mode,
            count=len(broker_positions),
        )

        # Update or create positions in database
        for broker_pos in broker_positions:
            # Check if position exists
            result = await db.execute(
                select(Position).where(
                    Position.user_id == current_user.id,
                    Position.mode == mode,
                    Position.symbol == broker_pos["symbol"]
                )
            )
            db_position = result.scalar_one_or_none()

            if db_position:
                # Update existing position
                db_position.quantity = broker_pos["quantity"]
                db_position.avg_entry_price = Decimal(broker_pos["avg_entry_price"])
                db_position.current_price = Decimal(broker_pos["current_price"])
                db_position.market_value = Decimal(broker_pos["market_value"])
                db_position.cost_basis = Decimal(broker_pos["cost_basis"])
                db_position.unrealized_pl = Decimal(broker_pos["unrealized_pl"])
                db_position.unrealized_pl_percent = Decimal(broker_pos["unrealized_pl_percent"])
            else:
                # Create new position
                db_position = Position(
                    user_id=current_user.id,
                    mode=TradingMode(mode),
                    symbol=broker_pos["symbol"],
                    quantity=broker_pos["quantity"],
                    avg_entry_price=Decimal(broker_pos["avg_entry_price"]),
                    current_price=Decimal(broker_pos["current_price"]),
                    market_value=Decimal(broker_pos["market_value"]),
                    cost_basis=Decimal(broker_pos["cost_basis"]),
                    unrealized_pl=Decimal(broker_pos["unrealized_pl"]),
                    unrealized_pl_percent=Decimal(broker_pos["unrealized_pl_percent"]),
                    broker_name="alpaca",
                )
                db.add(db_position)

        await db.commit()

        return {"success": True, "message": f"Synced {len(broker_positions)} positions"}

    except Exception as e:
        logger.error(
            "sync_positions_failed",
            user_id=str(current_user.id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync positions",
        )


# ============================================================================
# Account
# ============================================================================


@router.get("/account", response_model=AccountResponse)
async def get_account(
    mode: str = "paper",
    current_user: User = Depends(get_current_user),
):
    """
    Get account information from broker.

    Query parameters:
    - mode: Trading mode (paper or live)
    """
    try:
        broker = get_broker(mode=mode)
        account = await broker.get_account()

        return AccountResponse(
            cash=Decimal(account["cash"]),
            buying_power=Decimal(account["buying_power"]),
            equity=Decimal(account["equity"]),
            portfolio_value=Decimal(account["portfolio_value"]),
            currency=account.get("currency", "USD"),
            daytrade_count=account.get("daytrade_count"),
            pattern_day_trader=account.get("pattern_day_trader", False),
        )

    except Exception as e:
        logger.error(
            "get_account_failed",
            user_id=str(current_user.id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve account information",
        )


@router.get("/portfolio", response_model=PortfolioSummary)
async def get_portfolio_summary(
    mode: str = "paper",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get complete portfolio summary (account + positions).

    Query parameters:
    - mode: Trading mode (paper or live)
    """
    try:
        # Get account data
        broker = get_broker(mode=mode)
        account = await broker.get_account()

        # Get positions
        result = await db.execute(
            select(Position).where(
                Position.user_id == current_user.id,
                Position.mode == mode
            )
        )
        positions = result.scalars().all()

        # Calculate totals
        total_market_value = sum(p.market_value for p in positions)
        total_unrealized_pl = sum(p.unrealized_pl for p in positions)
        total_unrealized_pl_percent = (
            (total_unrealized_pl / total_market_value * 100) if total_market_value > 0 else Decimal("0")
        )

        return PortfolioSummary(
            account=AccountResponse(
                cash=Decimal(account["cash"]),
                buying_power=Decimal(account["buying_power"]),
                equity=Decimal(account["equity"]),
                portfolio_value=Decimal(account["portfolio_value"]),
                currency=account.get("currency", "USD"),
                daytrade_count=account.get("daytrade_count"),
                pattern_day_trader=account.get("pattern_day_trader", False),
            ),
            positions=positions,
            total_positions=len(positions),
            total_market_value=total_market_value,
            total_unrealized_pl=total_unrealized_pl,
            total_unrealized_pl_percent=total_unrealized_pl_percent,
        )

    except Exception as e:
        logger.error(
            "get_portfolio_summary_failed",
            user_id=str(current_user.id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve portfolio summary",
        )
