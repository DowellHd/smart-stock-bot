"""
Billing and subscription API endpoints.
"""
import stripe
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.redis import get_redis
from app.models.billing import SubscriptionPlan, UserSubscription
from app.models.user import User
from app.schemas.billing import (
    BillingPortalResponse,
    CancelSubscriptionResponse,
    CheckoutRequest,
    CheckoutResponse,
    SubscriptionPlanListResponse,
    SubscriptionResponse,
)
from app.services.billing import BillingService

logger = structlog.get_logger()

router = APIRouter()


# ============================================================================
# Subscription Plans
# ============================================================================


@router.get("/plans", response_model=SubscriptionPlanListResponse)
async def list_plans(db: AsyncSession = Depends(get_db)):
    """
    List all active subscription plans.

    Returns all available subscription plans (Free, Pro, etc.) with their
    features and pricing information.

    **Public endpoint** - no authentication required.
    """
    try:
        result = await db.execute(
            select(SubscriptionPlan)
            .where(SubscriptionPlan.is_active == True)  # noqa: E712
            .order_by(SubscriptionPlan.price_monthly)
        )
        plans = result.scalars().all()

        return SubscriptionPlanListResponse(plans=plans)

    except Exception as e:
        logger.error("failed_to_list_plans", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve subscription plans",
        )


# ============================================================================
# User Subscription Management
# ============================================================================


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current user's subscription details.

    Returns the user's active subscription including:
    - Current plan (Free, Pro, etc.)
    - Billing cycle and renewal date
    - Cancellation status
    - Trial information if applicable
    """
    try:
        billing_service = BillingService(db)

        # Query user subscription
        result = await db.execute(
            select(User).where(User.id == current_user.id).limit(1)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Get subscription (may be None for free users) - eagerly load plan and features
        subscription_result = await db.execute(
            select(UserSubscription)
            .options(selectinload(UserSubscription.plan).selectinload(SubscriptionPlan.features))
            .where(UserSubscription.user_id == current_user.id)
            .limit(1)
        )
        subscription = subscription_result.scalar_one_or_none()

        return SubscriptionResponse(
            subscription=subscription,
            message="No active subscription" if not subscription else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "failed_to_get_subscription",
            user_id=str(current_user.id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve subscription details",
        )


# ============================================================================
# Checkout & Payments
# ============================================================================


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    request: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create Stripe Checkout session to start a subscription.

    Generates a Stripe Checkout URL where the user can enter payment
    information to subscribe to a paid plan.

    **Flow:**
    1. User clicks "Upgrade to Pro"
    2. Frontend calls this endpoint
    3. Backend creates Stripe Checkout session
    4. Frontend redirects to Checkout URL
    5. User completes payment
    6. Stripe webhook activates subscription

    **Parameters:**
    - `plan_name`: Plan to subscribe to (e.g., 'pro')
    - `billing_cycle`: 'monthly' or 'yearly'
    - `success_url`: Where to redirect after successful payment
    - `cancel_url`: Where to redirect if payment is canceled
    """
    billing_service = BillingService(db)

    try:
        # Default URLs if not provided
        success_url = request.success_url or f"{settings.ALLOWED_ORIGINS[0]}/dashboard?checkout=success"
        cancel_url = request.cancel_url or f"{settings.ALLOWED_ORIGINS[0]}/pricing?checkout=canceled"

        result = await billing_service.create_checkout_session(
            user_id=current_user.id,
            plan_name=request.plan_name,
            billing_cycle=request.billing_cycle,
            success_url=success_url,
            cancel_url=cancel_url,
        )

        logger.info(
            "checkout_session_created",
            user_id=str(current_user.id),
            plan=request.plan_name,
            billing_cycle=request.billing_cycle,
        )

        return CheckoutResponse(**result)

    except ValueError as e:
        logger.error(
            "checkout_session_failed",
            user_id=str(current_user.id),
            error=str(e),
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(
            "checkout_session_error",
            user_id=str(current_user.id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session",
        )


@router.post("/cancel", response_model=CancelSubscriptionResponse)
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis),
):
    """
    Cancel user's subscription (keeps access until period end).

    Cancels the subscription but allows the user to continue using paid
    features until the end of their current billing period.

    **Important:**
    - User retains access until current period ends
    - No refund for remaining time
    - Can be reversed before period end via billing portal
    - After period ends, user is downgraded to Free plan
    """
    billing_service = BillingService(db)

    try:
        subscription = await billing_service.cancel_subscription(current_user.id, redis)

        logger.info("subscription_cancel_requested", user_id=str(current_user.id))

        return CancelSubscriptionResponse(
            message="Subscription will be canceled at the end of the current billing period",
            subscription=subscription,
        )

    except ValueError as e:
        logger.error(
            "subscription_cancel_failed",
            user_id=str(current_user.id),
            error=str(e),
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(
            "subscription_cancel_error",
            user_id=str(current_user.id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel subscription",
        )


@router.post("/portal", response_model=BillingPortalResponse)
async def get_customer_portal(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get Stripe customer portal URL for self-service billing management.

    Returns a URL to the Stripe Customer Portal where users can:
    - Update payment method
    - View invoices and payment history
    - Download receipts
    - Reactivate canceled subscriptions
    - Change billing information

    **Note:** Portal session expires after 1 hour.
    """
    billing_service = BillingService(db)

    try:
        portal_url = await billing_service.get_billing_portal_url(current_user.id)

        logger.info("billing_portal_requested", user_id=str(current_user.id))

        return BillingPortalResponse(portal_url=portal_url)

    except ValueError as e:
        logger.error(
            "billing_portal_failed",
            user_id=str(current_user.id),
            error=str(e),
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(
            "billing_portal_error",
            user_id=str(current_user.id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create billing portal session",
        )


# ============================================================================
# Stripe Webhooks
# ============================================================================


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis),
):
    """
    Handle Stripe webhook events.

    **Important:** This endpoint must be publicly accessible (no auth required)
    and configured in the Stripe Dashboard.

    **Webhook Events Handled:**
    - `checkout.session.completed` - Subscription activation
    - `customer.subscription.updated` - Status/period changes
    - `customer.subscription.deleted` - Subscription cancellation
    - `invoice.payment_failed` - Payment failures

    **Security:** Webhook signature verification using STRIPE_WEBHOOK_SECRET.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        logger.warning("stripe_webhook_missing_signature")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe signature header",
        )

    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )

        logger.info("stripe_webhook_received", event_type=event["type"], event_id=event["id"])

        # Handle event
        billing_service = BillingService(db)
        await billing_service.handle_webhook(event, redis)

        return {"status": "success"}

    except ValueError as e:
        logger.error("stripe_webhook_invalid_payload", error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload")

    except stripe.SignatureVerificationError as e:
        logger.error("stripe_webhook_invalid_signature", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature"
        )

    except Exception as e:
        logger.error("stripe_webhook_processing_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook",
        )
