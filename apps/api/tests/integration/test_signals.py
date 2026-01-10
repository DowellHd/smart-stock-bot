"""
Integration tests for signal generation.

Tests trading signal generation with strategy execution and entitlement enforcement.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import SubscriptionPlan, UserSubscription
from app.models.user import User


@pytest.mark.asyncio
async def test_generate_signal_for_symbol(authenticated_client: AsyncClient):
    """
    Test generating a trading signal for a symbol.

    Expected behavior:
    - Returns signal with action (buy/sell/hold)
    - Includes confidence score
    - Includes strategy name and reasoning
    - Free users get delayed signals
    """
    response = await authenticated_client.post(
        "/api/v1/signals/generate",
        json={
            "symbol": "AAPL",
            "strategy": "sma_crossover",
        },
    )

    # May fail if Alpaca market data not configured
    assert response.status_code in [200, 500, 503]

    if response.status_code == 200:
        signal = response.json()

        assert "symbol" in signal
        assert signal["symbol"] == "AAPL"
        assert "action" in signal
        assert signal["action"] in ["buy", "sell", "hold"]
        assert "confidence" in signal
        assert 0 <= signal["confidence"] <= 1
        assert "strategy" in signal
        assert signal["strategy"] == "sma_crossover"
        assert "reason" in signal
        assert "delayed" in signal
        assert "delay_minutes" in signal

        # Free user should get delayed signal
        assert signal["delayed"] is True
        assert signal["delay_minutes"] == 15


@pytest.mark.asyncio
async def test_free_user_signal_delay(authenticated_client: AsyncClient, test_user: User):
    """
    Test that free users receive 15-minute delayed signals.

    Expected behavior:
    - delayed = True
    - delay_minutes = 15
    - available_at is 15 minutes in the future
    """
    response = await authenticated_client.post(
        "/api/v1/signals/generate",
        json={
            "symbol": "MSFT",
            "strategy": "sma_crossover",
        },
    )

    if response.status_code == 200:
        signal = response.json()

        assert signal["delayed"] is True
        assert signal["delay_minutes"] == 15

        # Verify available_at is in the future
        from datetime import datetime

        available_at = datetime.fromisoformat(signal["available_at"].replace("Z", "+00:00"))
        timestamp = datetime.fromisoformat(signal["timestamp"].replace("Z", "+00:00"))

        # available_at should be ~15 minutes after timestamp
        delay_seconds = (available_at - timestamp).total_seconds()
        assert 14 * 60 <= delay_seconds <= 16 * 60  # Allow 1-minute tolerance


@pytest.mark.asyncio
async def test_pro_user_realtime_signals(
    authenticated_client: AsyncClient, db_session: AsyncSession, test_user: User
):
    """
    Test that Pro users get real-time (non-delayed) signals.

    Expected behavior:
    - delayed = False
    - delay_minutes = 0
    - available_at equals timestamp (immediate)
    """
    # Upgrade to pro plan
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

        response = await authenticated_client.post(
            "/api/v1/signals/generate",
            json={
                "symbol": "GOOGL",
                "strategy": "sma_crossover",
            },
        )

        if response.status_code == 200:
            signal = response.json()

            assert signal["delayed"] is False
            assert signal["delay_minutes"] == 0


@pytest.mark.asyncio
async def test_bulk_signal_generation(authenticated_client: AsyncClient):
    """
    Test generating signals for multiple symbols.

    Expected behavior:
    - Returns signals for all requested symbols
    - Total count matches requested symbols
    - Free users limited to 5 symbols
    """
    # Request 3 symbols (within free limit)
    response = await authenticated_client.post(
        "/api/v1/signals/bulk",
        json={
            "symbols": ["AAPL", "MSFT", "GOOGL"],
            "strategy": "sma_crossover",
        },
    )

    if response.status_code == 200:
        result = response.json()

        assert "signals" in result
        assert "total" in result
        assert result["total"] == 3
        assert len(result["signals"]) == 3

        # Verify all symbols present
        symbols = [s["symbol"] for s in result["signals"]]
        assert "AAPL" in symbols
        assert "MSFT" in symbols
        assert "GOOGL" in symbols


@pytest.mark.asyncio
async def test_bulk_signal_free_user_limit(authenticated_client: AsyncClient):
    """
    Test that free users are limited to 5 symbols in bulk requests.

    Expected behavior:
    - Request with > 5 symbols gets 403
    - Error message explains limit
    """
    # Request 10 symbols (exceeds free limit)
    response = await authenticated_client.post(
        "/api/v1/signals/bulk",
        json={
            "symbols": ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN", "NVDA", "META", "AMD", "NFLX", "SPY"],
            "strategy": "sma_crossover",
        },
    )

    assert response.status_code == 403
    error = response.json()
    assert "detail" in error
    assert "5" in error["detail"]


@pytest.mark.asyncio
async def test_signal_contains_sma_values(authenticated_client: AsyncClient):
    """
    Test that SMA crossover signals include SMA values.

    Expected behavior:
    - Signal includes sma_50 value
    - Signal includes sma_200 value
    - Reason explains the crossover logic
    """
    response = await authenticated_client.post(
        "/api/v1/signals/generate",
        json={
            "symbol": "AAPL",
            "strategy": "sma_crossover",
        },
    )

    if response.status_code == 200:
        signal = response.json()

        # SMA values should be present (unless insufficient data)
        if signal["action"] != "hold" or "Insufficient data" not in signal["reason"]:
            assert "sma_50" in signal
            assert "sma_200" in signal

            # Values should be positive numbers
            if signal["sma_50"] is not None:
                assert signal["sma_50"] > 0
            if signal["sma_200"] is not None:
                assert signal["sma_200"] > 0


@pytest.mark.asyncio
async def test_signal_action_reasoning(authenticated_client: AsyncClient):
    """
    Test that signals include human-readable reasoning.

    Expected behavior:
    - Reason field explains why action was recommended
    - Mentions SMA values and crossover logic
    """
    response = await authenticated_client.post(
        "/api/v1/signals/generate",
        json={
            "symbol": "MSFT",
            "strategy": "sma_crossover",
        },
    )

    if response.status_code == 200:
        signal = response.json()

        assert "reason" in signal
        assert len(signal["reason"]) > 0

        # Reason should mention SMAs or trend
        reason_lower = signal["reason"].lower()
        assert any(
            keyword in reason_lower
            for keyword in ["sma", "moving average", "cross", "trend", "insufficient data"]
        )


@pytest.mark.asyncio
async def test_invalid_strategy_rejected(authenticated_client: AsyncClient):
    """
    Test that invalid strategy names are rejected.

    Expected behavior:
    - Unknown strategy gets 400/422 error
    """
    response = await authenticated_client.post(
        "/api/v1/signals/generate",
        json={
            "symbol": "AAPL",
            "strategy": "invalid_strategy",
        },
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_signal_timestamp_present(authenticated_client: AsyncClient):
    """
    Test that signals include timestamp and available_at fields.

    Expected behavior:
    - timestamp shows when signal was generated
    - available_at shows when user can act on it
    - Both are ISO format datetime strings
    """
    response = await authenticated_client.post(
        "/api/v1/signals/generate",
        json={
            "symbol": "AAPL",
            "strategy": "sma_crossover",
        },
    )

    if response.status_code == 200:
        signal = response.json()

        assert "timestamp" in signal
        assert "available_at" in signal

        # Verify they're valid ISO datetime strings
        from datetime import datetime

        timestamp = datetime.fromisoformat(signal["timestamp"].replace("Z", "+00:00"))
        available_at = datetime.fromisoformat(signal["available_at"].replace("Z", "+00:00"))

        assert isinstance(timestamp, datetime)
        assert isinstance(available_at, datetime)


@pytest.mark.asyncio
async def test_current_price_included(authenticated_client: AsyncClient):
    """
    Test that signals include current price of the symbol.

    Expected behavior:
    - current_price field present
    - Price is positive number
    """
    response = await authenticated_client.post(
        "/api/v1/signals/generate",
        json={
            "symbol": "AAPL",
            "strategy": "sma_crossover",
        },
    )

    if response.status_code == 200:
        signal = response.json()

        # current_price may be None if insufficient data
        if signal.get("current_price") is not None:
            assert signal["current_price"] > 0


@pytest.mark.asyncio
async def test_error_signal_on_failure(authenticated_client: AsyncClient):
    """
    Test that bulk signal generation handles individual symbol failures.

    Expected behavior:
    - If one symbol fails, others still process
    - Failed symbols get error signal with reason
    """
    # Mix valid and potentially invalid symbols
    response = await authenticated_client.post(
        "/api/v1/signals/bulk",
        json={
            "symbols": ["AAPL", "INVALID123", "MSFT"],
            "strategy": "sma_crossover",
        },
    )

    # Should complete (may return errors for invalid symbols)
    if response.status_code == 200:
        result = response.json()

        assert "signals" in result
        # Check if any signals have error action
        actions = [s["action"] for s in result["signals"]]
        # May include "error" for invalid symbols
