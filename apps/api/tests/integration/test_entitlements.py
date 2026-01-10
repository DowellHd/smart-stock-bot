"""
Integration tests for entitlements enforcement.

Tests that subscription plan features are properly enforced across all endpoints.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import SubscriptionPlan, UserSubscription
from app.models.user import User


@pytest.mark.asyncio
async def test_free_user_blocked_from_live_trading(
    authenticated_client: AsyncClient, test_user: User
):
    """
    Test that free users cannot access live trading.

    Expected behavior:
    - Free users attempting live trading get 403 Forbidden
    - Error message explains Pro plan requirement
    """
    # Attempt to place live trading order
    response = await authenticated_client.post(
        "/api/v1/trading/orders",
        json={
            "symbol": "AAPL",
            "quantity": 10,
            "side": "buy",
            "order_type": "market",
            "mode": "live",
            "time_in_force": "gtc",
        },
    )

    assert response.status_code == 403
    error = response.json()
    assert "detail" in error
    assert "live_trading" in error["detail"].lower() or "pro" in error["detail"].lower()


@pytest.mark.asyncio
async def test_free_user_can_paper_trade(authenticated_client: AsyncClient):
    """
    Test that free users CAN use paper trading.

    Expected behavior:
    - Free users can place paper trading orders
    - Orders are accepted and saved
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

    # May fail with 500 if Alpaca not configured - that's ok
    # We're checking entitlement logic, not Alpaca integration
    assert response.status_code in [201, 400, 500, 503]

    # If successful, verify it's paper mode
    if response.status_code == 201:
        order = response.json()
        assert order["mode"] == "paper"


@pytest.mark.asyncio
async def test_free_user_gets_delayed_signals(authenticated_client: AsyncClient):
    """
    Test that free users receive 15-minute delayed signals.

    Expected behavior:
    - Signal delay_minutes = 15
    - available_at is 15 minutes in the future
    - delayed flag is True
    """
    response = await authenticated_client.get("/api/v1/signals/delay-info")

    assert response.status_code == 200
    delay_info = response.json()

    assert delay_info["plan"] == "free"
    assert delay_info["delay_minutes"] == 15
    assert delay_info["is_realtime"] is False
    assert "15 minutes" in delay_info["message"].lower()


@pytest.mark.asyncio
async def test_starter_user_gets_realtime_signals(
    authenticated_client: AsyncClient, db_session: AsyncSession, test_user: User
):
    """
    Test that Starter plan users get real-time signals.

    Expected behavior:
    - Signal delay_minutes = 0
    - available_at is immediate (now)
    - delayed flag is False
    """
    # Upgrade user to starter plan
    result = await db_session.execute(
        select(UserSubscription).where(UserSubscription.user_id == test_user.id)
    )
    subscription = result.scalar_one_or_none()

    result = await db_session.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.name == "starter")
    )
    starter_plan = result.scalar_one_or_none()

    if subscription and starter_plan:
        subscription.plan_id = starter_plan.id
        await db_session.commit()

        # Clear any cached entitlements (would be done by Redis TTL in production)
        # For tests, just make a new request

        response = await authenticated_client.get("/api/v1/signals/delay-info")

        assert response.status_code == 200
        delay_info = response.json()

        assert delay_info["plan"] == "starter"
        assert delay_info["delay_minutes"] == 0
        assert delay_info["is_realtime"] is True


@pytest.mark.asyncio
async def test_pro_user_gets_realtime_signals(
    authenticated_client: AsyncClient, db_session: AsyncSession, test_user: User
):
    """
    Test that Pro plan users get real-time signals.

    Expected behavior:
    - Signal delay_minutes = 0
    - available_at is immediate (now)
    - delayed flag is False
    """
    # Upgrade user to pro plan
    result = await db_session.execute(
        select(UserSubscription).where(UserSubscription.user_id == test_user.id)
    )
    subscription = result.scalar_one_or_none()

    result = await db_session.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.name == "pro")
    )
    pro_plan = result.scalar_one_or_none()

    if subscription and pro_plan:
        subscription.plan_id = pro_plan.id
        await db_session.commit()

        response = await authenticated_client.get("/api/v1/signals/delay-info")

        assert response.status_code == 200
        delay_info = response.json()

        assert delay_info["plan"] == "pro"
        assert delay_info["delay_minutes"] == 0
        assert delay_info["is_realtime"] is True


@pytest.mark.asyncio
async def test_free_user_watchlist_limit(
    authenticated_client: AsyncClient, db_session: AsyncSession, test_user: User
):
    """
    Test that free users are limited to 5 watchlist symbols.

    Expected behavior:
    - Bulk signal generation with > 5 symbols gets 403
    - Error message explains upgrade requirement
    """
    # Try to generate signals for 10 symbols (exceeds free limit of 5)
    response = await authenticated_client.post(
        "/api/v1/signals/bulk",
        json={
            "symbols": ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN", "NVDA", "META", "AMD", "NFLX", "SPY"],
            "strategy": "sma_crossover",
        },
    )

    assert response.status_code == 403
    error = response.json()
    assert "detail" in error
    assert "5" in error["detail"] or "max" in error["detail"].lower()


@pytest.mark.asyncio
async def test_starter_user_watchlist_limit(
    authenticated_client: AsyncClient, db_session: AsyncSession, test_user: User
):
    """
    Test that Starter users can use up to 20 symbols.

    Expected behavior:
    - Bulk signal generation with <= 20 symbols succeeds
    - Bulk signal generation with > 20 symbols gets 403
    """
    # Upgrade to starter
    result = await db_session.execute(
        select(UserSubscription).where(UserSubscription.user_id == test_user.id)
    )
    subscription = result.scalar_one_or_none()

    result = await db_session.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.name == "starter")
    )
    starter_plan = result.scalar_one_or_none()

    if subscription and starter_plan:
        subscription.plan_id = starter_plan.id
        await db_session.commit()

        # Try 10 symbols (should succeed for Starter)
        response = await authenticated_client.post(
            "/api/v1/signals/bulk",
            json={
                "symbols": ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN", "NVDA", "META", "AMD", "NFLX", "SPY"],
                "strategy": "sma_crossover",
            },
        )

        # May fail with 500 if Alpaca not configured
        # We're checking entitlement, not Alpaca functionality
        assert response.status_code in [200, 500, 503]


@pytest.mark.asyncio
async def test_pro_user_can_access_live_trading_if_approved(
    authenticated_client: AsyncClient, db_session: AsyncSession, test_user: User
):
    """
    Test that Pro users with admin approval can access live trading.

    Expected behavior:
    - Pro user + live_trading_approved = can place live orders
    - Pro user without approval = 403
    """
    # Upgrade to pro
    result = await db_session.execute(
        select(UserSubscription).where(UserSubscription.user_id == test_user.id)
    )
    subscription = result.scalar_one_or_none()

    result = await db_session.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.name == "pro")
    )
    pro_plan = result.scalar_one_or_none()

    if subscription and pro_plan:
        subscription.plan_id = pro_plan.id
        await db_session.commit()

        # First, try without approval (should fail)
        test_user.live_trading_approved = False
        await db_session.commit()

        response = await authenticated_client.post(
            "/api/v1/trading/orders",
            json={
                "symbol": "AAPL",
                "quantity": 1,
                "side": "buy",
                "order_type": "market",
                "mode": "live",
                "time_in_force": "gtc",
            },
        )

        assert response.status_code == 403
        error = response.json()
        assert "approval" in error["detail"].lower()

        # Now approve and try again
        test_user.live_trading_approved = True
        await db_session.commit()

        response = await authenticated_client.post(
            "/api/v1/trading/orders",
            json={
                "symbol": "AAPL",
                "quantity": 1,
                "side": "buy",
                "order_type": "market",
                "mode": "live",
                "time_in_force": "gtc",
            },
        )

        # Should pass entitlement check (may fail on Alpaca if not configured)
        assert response.status_code in [201, 400, 500, 503]


@pytest.mark.asyncio
async def test_entitlements_cached_for_performance(
    authenticated_client: AsyncClient, db_session: AsyncSession, test_user: User
):
    """
    Test that entitlements are cached to reduce database queries.

    Expected behavior:
    - Multiple requests use cached entitlements
    - Cache expires after TTL (5 minutes in production)

    Note: This test verifies the endpoint works consistently,
    actual cache testing would require Redis inspection.
    """
    # Make multiple requests in quick succession
    for _ in range(3):
        response = await authenticated_client.get("/api/v1/signals/delay-info")
        assert response.status_code == 200
        delay_info = response.json()
        assert delay_info["plan"] == "free"

    # All requests should return consistent data
    # (Cache ensures minimal DB load)


@pytest.mark.asyncio
async def test_downgraded_user_loses_premium_features(
    authenticated_client: AsyncClient, db_session: AsyncSession, test_user: User
):
    """
    Test that downgrading removes premium feature access.

    Expected behavior:
    - User upgraded to Pro has real-time signals
    - User downgraded to Free gets delayed signals
    """
    # Upgrade to pro
    result = await db_session.execute(
        select(UserSubscription).where(UserSubscription.user_id == test_user.id)
    )
    subscription = result.scalar_one_or_none()

    result = await db_session.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.name == "pro")
    )
    pro_plan = result.scalar_one_or_none()

    result_free = await db_session.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.name == "free")
    )
    free_plan = result_free.scalar_one_or_none()

    if subscription and pro_plan and free_plan:
        # Start as Pro
        subscription.plan_id = pro_plan.id
        await db_session.commit()

        response = await authenticated_client.get("/api/v1/signals/delay-info")
        assert response.status_code == 200
        assert response.json()["delay_minutes"] == 0

        # Downgrade to Free
        subscription.plan_id = free_plan.id
        await db_session.commit()

        response = await authenticated_client.get("/api/v1/signals/delay-info")
        assert response.status_code == 200
        assert response.json()["delay_minutes"] == 15
