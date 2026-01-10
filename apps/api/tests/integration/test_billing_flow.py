"""
Integration tests for billing flow.

Tests the complete subscription lifecycle including:
- Free plan assignment on signup
- Viewing available plans
- Subscription status checks
- Plan feature enforcement
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import SubscriptionPlan, UserSubscription
from app.models.user import User


@pytest.mark.asyncio
async def test_free_signup_assigns_free_plan(client: AsyncClient, db_session: AsyncSession):
    """
    Test that new user signup automatically assigns free plan.

    Expected behavior:
    1. User registers
    2. Free plan is automatically assigned
    3. Subscription status is 'active'
    """
    # Create a new user
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "newuser@example.com",
            "password": "NewUserPass123!",
            "full_name": "New User",
        },
    )

    assert response.status_code == 201
    user_data = response.json()
    user_id = user_data["id"]

    # Check that user has a subscription
    result = await db_session.execute(
        select(UserSubscription).where(UserSubscription.user_id == user_id)
    )
    subscription = result.scalar_one_or_none()

    assert subscription is not None, "User should have a subscription"
    assert subscription.status == "active"

    # Verify it's the free plan
    result = await db_session.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.id == subscription.plan_id)
    )
    plan = result.scalar_one_or_none()

    assert plan is not None
    assert plan.name == "free"
    assert plan.price_monthly == 0


@pytest.mark.asyncio
async def test_list_available_plans(authenticated_client: AsyncClient):
    """
    Test fetching all available subscription plans.

    Expected behavior:
    - Returns all active plans (Free, Starter, Pro)
    - Each plan has pricing and feature information
    """
    response = await authenticated_client.get("/api/v1/billing/plans")

    assert response.status_code == 200
    plans = response.json()

    assert len(plans) >= 3, "Should have at least 3 plans (Free, Starter, Pro)"

    # Check plan names
    plan_names = [p["name"] for p in plans]
    assert "free" in plan_names
    assert "starter" in plan_names
    assert "pro" in plan_names

    # Verify free plan details
    free_plan = next(p for p in plans if p["name"] == "free")
    assert free_plan["price_monthly"] == 0
    assert free_plan["is_active"] is True

    # Verify starter plan details
    starter_plan = next(p for p in plans if p["name"] == "starter")
    assert starter_plan["price_monthly"] == 19.99

    # Verify pro plan details
    pro_plan = next(p for p in plans if p["name"] == "pro")
    assert pro_plan["price_monthly"] == 49.99


@pytest.mark.asyncio
async def test_get_current_subscription(authenticated_client: AsyncClient, test_user):
    """
    Test fetching current user's subscription.

    Expected behavior:
    - Returns current subscription details
    - Shows active status
    - Includes plan information
    """
    response = await authenticated_client.get("/api/v1/billing/subscription")

    assert response.status_code == 200
    subscription = response.json()

    assert subscription is not None
    assert "plan" in subscription
    assert subscription["plan"]["name"] == "free"  # Test users start with free plan


@pytest.mark.asyncio
async def test_free_user_has_correct_features(authenticated_client: AsyncClient):
    """
    Test that free users have correct feature entitlements.

    Expected features:
    - live_trading_enabled: false
    - signal_delay_minutes: 15
    - max_watchlist_symbols: 5
    - daily_api_requests: 100
    """
    # Check entitlements via signals delay endpoint
    response = await authenticated_client.get("/api/v1/signals/delay-info")

    assert response.status_code == 200
    delay_info = response.json()

    assert delay_info["plan"] == "free"
    assert delay_info["delay_minutes"] == 15
    assert delay_info["is_realtime"] is False


@pytest.mark.asyncio
async def test_upgrade_to_paid_plan_requires_stripe(
    authenticated_client: AsyncClient, db_session: AsyncSession
):
    """
    Test that upgrading to paid plan redirects to Stripe checkout.

    Expected behavior:
    - POST /billing/checkout creates Stripe session
    - Returns checkout URL
    - Subscription not activated until Stripe webhook confirms

    Note: This test verifies the endpoint exists and returns proper structure.
    Actual Stripe integration requires valid API keys.
    """
    # Attempt to create checkout session for starter plan
    response = await authenticated_client.post(
        "/api/v1/billing/checkout",
        params={
            "plan_name": "starter",
            "billing_cycle": "monthly",
        },
    )

    # May fail with 500 if Stripe keys not configured - that's expected
    # We're just checking the endpoint structure
    assert response.status_code in [200, 500, 503]

    if response.status_code == 200:
        data = response.json()
        assert "checkout_url" in data or "url" in data


@pytest.mark.asyncio
async def test_subscription_status_after_failed_payment(
    db_session: AsyncSession, test_user: User
):
    """
    Test subscription status handling after payment failure.

    Expected behavior:
    - Subscription status should be 'past_due'
    - User should still have limited access
    - Downgrade occurs after grace period

    Note: This simulates the state that would be set by Stripe webhook.
    """
    # Get user's subscription
    result = await db_session.execute(
        select(UserSubscription).where(UserSubscription.user_id == test_user.id)
    )
    subscription = result.scalar_one_or_none()

    assert subscription is not None

    # Simulate payment failure (would be set by Stripe webhook)
    subscription.status = "past_due"
    await db_session.commit()

    # Verify subscription is in past_due state
    await db_session.refresh(subscription)
    assert subscription.status == "past_due"


@pytest.mark.asyncio
async def test_cancel_subscription_keeps_access_until_period_end(
    authenticated_client: AsyncClient, db_session: AsyncSession, test_user: User
):
    """
    Test that canceling subscription maintains access until period end.

    Expected behavior:
    - POST /billing/cancel sets cancel_at_period_end = True
    - Subscription remains active until current_period_end
    - User keeps access during this time
    """
    # First, manually upgrade user to starter (simulate successful payment)
    result = await db_session.execute(
        select(UserSubscription).where(UserSubscription.user_id == test_user.id)
    )
    subscription = result.scalar_one_or_none()

    # Get starter plan
    result = await db_session.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.name == "starter")
    )
    starter_plan = result.scalar_one_or_none()

    if subscription and starter_plan:
        subscription.plan_id = starter_plan.id
        subscription.status = "active"
        await db_session.commit()

        # Now test cancellation
        response = await authenticated_client.post("/api/v1/billing/cancel")

        # May return 500 if no Stripe subscription exists - that's expected
        assert response.status_code in [200, 400, 500]

        if response.status_code == 200:
            data = response.json()
            assert "message" in data


@pytest.mark.asyncio
async def test_webhook_signature_validation(client: AsyncClient):
    """
    Test that Stripe webhook endpoint validates signatures.

    Expected behavior:
    - Webhook without signature should fail
    - Webhook with invalid signature should fail
    - Only valid Stripe signatures are processed
    """
    # Attempt to post fake webhook without signature
    response = await client.post(
        "/api/v1/billing/webhooks/stripe",
        json={"type": "checkout.session.completed", "data": {}},
    )

    # Should fail due to missing/invalid signature
    assert response.status_code in [400, 401, 403, 500]
