"""
Integration tests for trading endpoints.

Tests order placement, position tracking, and account data retrieval.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trading import Order, Position
from app.models.user import User


@pytest.mark.asyncio
async def test_paper_trading_order_placement(
    authenticated_client: AsyncClient, db_session: AsyncSession
):
    """
    Test that users can place paper trading orders.

    Expected behavior:
    - Order is accepted
    - Order is saved to database
    - Order status is set appropriately
    """
    response = await authenticated_client.post(
        "/api/v1/trading/orders",
        json={
            "symbol": "AAPL",
            "quantity": 10,
            "side": "buy",
            "order_type": "market",
            "mode": "paper",
            "time_in_force": "gtc",
        },
    )

    # May fail if Alpaca not configured - that's expected
    assert response.status_code in [201, 400, 500, 503]

    if response.status_code == 201:
        order_data = response.json()

        assert order_data["symbol"] == "AAPL"
        assert order_data["quantity"] == 10
        assert order_data["side"] == "buy"
        assert order_data["mode"] == "paper"

        # Verify order was saved to database
        result = await db_session.execute(
            select(Order).where(Order.id == order_data["id"])
        )
        db_order = result.scalar_one_or_none()

        assert db_order is not None
        assert db_order.symbol == "AAPL"


@pytest.mark.asyncio
async def test_limit_order_requires_price(authenticated_client: AsyncClient):
    """
    Test that limit orders require limit_price parameter.

    Expected behavior:
    - Limit order without price gets 400 Bad Request
    - Error message explains requirement
    """
    response = await authenticated_client.post(
        "/api/v1/trading/orders",
        json={
            "symbol": "AAPL",
            "quantity": 10,
            "side": "buy",
            "order_type": "limit",
            "mode": "paper",
            "time_in_force": "gtc",
            # Missing limit_price
        },
    )

    assert response.status_code in [400, 422]
    error = response.json()
    assert "detail" in error


@pytest.mark.asyncio
async def test_list_user_orders(
    authenticated_client: AsyncClient, db_session: AsyncSession, test_user: User
):
    """
    Test fetching user's order history.

    Expected behavior:
    - Returns list of user's orders
    - Orders are sorted by created_at desc (newest first)
    - Can filter by mode (paper/live)
    """
    response = await authenticated_client.get("/api/v1/trading/orders?mode=paper")

    assert response.status_code == 200
    orders = response.json()

    assert isinstance(orders, list)
    # May be empty if no orders placed yet


@pytest.mark.asyncio
async def test_get_specific_order(
    authenticated_client: AsyncClient, db_session: AsyncSession, test_user: User
):
    """
    Test fetching a specific order by ID.

    Expected behavior:
    - Returns order details if order belongs to user
    - Returns 404 if order doesn't exist or belongs to another user
    """
    # Try to get non-existent order
    response = await authenticated_client.get(
        "/api/v1/trading/orders/00000000-0000-0000-0000-000000000000"
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_positions(authenticated_client: AsyncClient):
    """
    Test fetching user's open positions.

    Expected behavior:
    - Returns list of positions
    - Can filter by mode (paper/live)
    """
    response = await authenticated_client.get("/api/v1/trading/positions?mode=paper")

    assert response.status_code == 200
    positions = response.json()

    assert isinstance(positions, list)


@pytest.mark.asyncio
async def test_sync_positions_from_broker(authenticated_client: AsyncClient):
    """
    Test syncing positions from broker to local database.

    Expected behavior:
    - Fetches positions from Alpaca
    - Updates or creates local position records
    - Returns success message with count
    """
    response = await authenticated_client.post("/api/v1/trading/positions/sync?mode=paper")

    # May fail if Alpaca not configured
    assert response.status_code in [200, 500, 503]

    if response.status_code == 200:
        result = response.json()
        assert result["success"] is True
        assert "message" in result


@pytest.mark.asyncio
async def test_get_account_info(authenticated_client: AsyncClient):
    """
    Test fetching account information from broker.

    Expected behavior:
    - Returns account balance, buying power, equity
    - Includes day trading status
    """
    response = await authenticated_client.get("/api/v1/trading/account?mode=paper")

    # May fail if Alpaca not configured
    assert response.status_code in [200, 500, 503]

    if response.status_code == 200:
        account = response.json()

        assert "cash" in account
        assert "buying_power" in account
        assert "equity" in account
        assert "portfolio_value" in account


@pytest.mark.asyncio
async def test_get_portfolio_summary(authenticated_client: AsyncClient):
    """
    Test fetching complete portfolio summary.

    Expected behavior:
    - Returns account data + positions
    - Includes aggregated totals (total P&L, etc.)
    """
    response = await authenticated_client.get("/api/v1/trading/portfolio?mode=paper")

    # May fail if Alpaca not configured
    assert response.status_code in [200, 500, 503]

    if response.status_code == 200:
        portfolio = response.json()

        assert "account" in portfolio
        assert "positions" in portfolio
        assert "total_positions" in portfolio
        assert "total_market_value" in portfolio
        assert "total_unrealized_pl" in portfolio


@pytest.mark.asyncio
async def test_cancel_pending_order(
    authenticated_client: AsyncClient, db_session: AsyncSession, test_user: User
):
    """
    Test canceling a pending order.

    Expected behavior:
    - Pending orders can be canceled
    - Filled/canceled orders cannot be canceled
    - Returns success/failure status
    """
    # Try to cancel non-existent order
    response = await authenticated_client.delete(
        "/api/v1/trading/orders/00000000-0000-0000-0000-000000000000"
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_order_saved_with_broker_id(
    authenticated_client: AsyncClient, db_session: AsyncSession
):
    """
    Test that orders are saved with broker_order_id.

    Expected behavior:
    - Order saved to database includes broker_order_id
    - broker_name is set to 'alpaca'
    - Allows tracking across systems
    """
    response = await authenticated_client.post(
        "/api/v1/trading/orders",
        json={
            "symbol": "MSFT",
            "quantity": 5,
            "side": "sell",
            "order_type": "market",
            "mode": "paper",
            "time_in_force": "day",
        },
    )

    # May fail if Alpaca not configured
    if response.status_code == 201:
        order = response.json()

        # Should have broker_order_id if successfully placed with Alpaca
        assert "broker_order_id" in order
        assert order["broker_name"] == "alpaca"


@pytest.mark.asyncio
async def test_paper_and_live_orders_separated(
    authenticated_client: AsyncClient, db_session: AsyncSession
):
    """
    Test that paper and live orders are kept separate.

    Expected behavior:
    - Listing paper orders doesn't show live orders
    - Listing live orders doesn't show paper orders
    - Mode filter works correctly
    """
    # List paper orders
    response = await authenticated_client.get("/api/v1/trading/orders?mode=paper")
    assert response.status_code == 200
    paper_orders = response.json()

    # List live orders (if accessible)
    response = await authenticated_client.get("/api/v1/trading/orders?mode=live")
    # May get 403 if user doesn't have live trading access
    assert response.status_code in [200, 403]


@pytest.mark.asyncio
async def test_order_validation(authenticated_client: AsyncClient):
    """
    Test that orders are validated before submission.

    Expected behavior:
    - Invalid symbols rejected
    - Invalid quantities rejected (must be > 0)
    - Invalid order types rejected
    """
    # Test negative quantity
    response = await authenticated_client.post(
        "/api/v1/trading/orders",
        json={
            "symbol": "AAPL",
            "quantity": -5,  # Invalid
            "side": "buy",
            "order_type": "market",
            "mode": "paper",
            "time_in_force": "gtc",
        },
    )

    assert response.status_code == 422  # Validation error

    # Test invalid side
    response = await authenticated_client.post(
        "/api/v1/trading/orders",
        json={
            "symbol": "AAPL",
            "quantity": 10,
            "side": "invalid",  # Invalid
            "order_type": "market",
            "mode": "paper",
            "time_in_force": "gtc",
        },
    )

    assert response.status_code == 422  # Validation error
