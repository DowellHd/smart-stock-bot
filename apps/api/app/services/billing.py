"""
Billing service for Stripe subscription management.
"""
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

import stripe
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.entitlements import invalidate_entitlements_cache
from app.models.billing import SubscriptionPlan, SubscriptionStatus, UserSubscription
from app.models.user import AuditLog, User

logger = structlog.get_logger()

# Initialize Stripe with production secret key
stripe.api_key = settings.STRIPE_SECRET_KEY


class BillingService:
    """Service for managing billing and subscriptions via Stripe."""

    def __init__(self, db: AsyncSession):
        """
        Initialize billing service.

        Args:
            db: Database session
        """
        self.db = db

    async def create_customer(self, user: User) -> str:
        """
        Create Stripe customer for user.

        Args:
            user: User to create customer for

        Returns:
            Stripe customer ID

        Raises:
            ValueError: If customer already exists
        """
        # Check if customer already exists
        result = await self.db.execute(
            select(UserSubscription).where(UserSubscription.user_id == user.id).limit(1)
        )
        existing = result.scalar_one_or_none()

        if existing and existing.stripe_customer_id:
            logger.info(
                "stripe_customer_already_exists",
                user_id=str(user.id),
                customer_id=existing.stripe_customer_id,
            )
            return existing.stripe_customer_id

        # Create Stripe customer
        try:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.full_name,
                metadata={"user_id": str(user.id)},
            )

            logger.info(
                "stripe_customer_created",
                user_id=str(user.id),
                customer_id=customer.id,
            )

            return customer.id

        except stripe.StripeError as e:
            logger.error(
                "stripe_customer_creation_failed",
                user_id=str(user.id),
                error=str(e),
                exc_info=True,
            )
            raise ValueError(f"Failed to create Stripe customer: {str(e)}")

    async def create_checkout_session(
        self,
        user_id: UUID,
        plan_name: str,
        billing_cycle: str,
        success_url: str,
        cancel_url: str,
    ) -> Dict[str, str]:
        """
        Create Stripe Checkout session for subscription.

        Args:
            user_id: User ID
            plan_name: Plan name (e.g., 'pro')
            billing_cycle: 'monthly' or 'yearly'
            success_url: URL to redirect after successful checkout
            cancel_url: URL to redirect after canceled checkout

        Returns:
            Dictionary with checkout_url and session_id

        Raises:
            ValueError: If plan not found or Stripe error
        """
        # Fetch user
        user_result = await self.db.execute(select(User).where(User.id == user_id).limit(1))
        user = user_result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found")

        # Fetch plan
        plan_result = await self.db.execute(
            select(SubscriptionPlan).where(
                SubscriptionPlan.name == plan_name,
                SubscriptionPlan.is_active == True,  # noqa: E712
            ).limit(1)
        )
        plan = plan_result.scalar_one_or_none()

        if not plan:
            raise ValueError(f"Plan '{plan_name}' not found or inactive")

        # Get Stripe price ID
        if billing_cycle == "monthly":
            price_id = plan.stripe_price_id_monthly
        elif billing_cycle == "yearly":
            price_id = plan.stripe_price_id_yearly
        else:
            raise ValueError("billing_cycle must be 'monthly' or 'yearly'")

        if not price_id:
            raise ValueError(f"No Stripe price ID configured for {plan_name} {billing_cycle}")

        # Create or get customer
        customer_id = await self.create_customer(user)

        # Create checkout session
        try:
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=["card"],
                line_items=[{"price": price_id, "quantity": 1}],
                mode="subscription",
                success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=cancel_url,
                metadata={
                    "user_id": str(user_id),
                    "plan_id": str(plan.id),
                    "plan_name": plan_name,
                    "billing_cycle": billing_cycle,
                },
                allow_promotion_codes=True,
                billing_address_collection="required",
                subscription_data={
                    "metadata": {
                        "user_id": str(user_id),
                        "plan_name": plan_name,
                    }
                },
            )

            logger.info(
                "stripe_checkout_session_created",
                user_id=str(user_id),
                plan=plan_name,
                billing_cycle=billing_cycle,
                session_id=session.id,
            )

            return {"checkout_url": session.url, "session_id": session.id}

        except stripe.StripeError as e:
            logger.error(
                "stripe_checkout_session_failed",
                user_id=str(user_id),
                error=str(e),
                exc_info=True,
            )
            raise ValueError(f"Failed to create checkout session: {str(e)}")

    async def handle_webhook(self, event: stripe.Event, redis) -> None:
        """
        Handle Stripe webhook events with idempotency.

        Args:
            event: Stripe event object
            redis: Redis client

        Raises:
            ValueError: If event handling fails
        """
        event_type = event["type"]
        event_id = event["id"]

        # Idempotency check - prevent duplicate processing
        idempotency_key = f"webhook_processed:{event_id}"
        already_processed = await redis.get(idempotency_key)

        if already_processed:
            logger.info(
                "webhook_already_processed_skipping",
                event_type=event_type,
                event_id=event_id,
            )
            return

        logger.info("stripe_webhook_received", event_type=event_type, event_id=event_id)

        try:
            if event_type == "checkout.session.completed":
                await self._handle_checkout_completed(event["data"]["object"], redis)

            elif event_type == "customer.subscription.updated":
                await self._handle_subscription_updated(event["data"]["object"], redis)

            elif event_type == "customer.subscription.deleted":
                await self._handle_subscription_deleted(event["data"]["object"], redis)

            elif event_type == "invoice.payment_failed":
                await self._handle_payment_failed(event["data"]["object"], redis)

            elif event_type == "invoice.payment_succeeded":
                await self._handle_payment_succeeded(event["data"]["object"], redis)

            elif event_type == "customer.updated":
                await self._handle_customer_updated(event["data"]["object"], redis)

            else:
                logger.info("stripe_webhook_ignored", event_type=event_type)

            # Mark event as processed (24-hour TTL)
            await redis.setex(idempotency_key, 86400, "1")

            logger.info(
                "stripe_webhook_processed_successfully",
                event_type=event_type,
                event_id=event_id,
            )

        except Exception as e:
            logger.error(
                "stripe_webhook_handling_failed",
                event_type=event_type,
                event_id=event_id,
                error=str(e),
                exc_info=True,
            )
            raise ValueError(f"Failed to handle webhook: {str(e)}")

    async def _handle_checkout_completed(self, session: Dict[str, Any], redis) -> None:
        """Handle checkout.session.completed event."""
        user_id_str = session["metadata"]["user_id"]
        plan_id_str = session["metadata"]["plan_id"]
        customer_id = session["customer"]
        subscription_id = session["subscription"]

        user_id = UUID(user_id_str)
        plan_id = UUID(plan_id_str)

        # Fetch or create user subscription
        result = await self.db.execute(
            select(UserSubscription).where(UserSubscription.user_id == user_id).limit(1)
        )
        user_subscription = result.scalar_one_or_none()

        if user_subscription:
            # Update existing subscription
            user_subscription.plan_id = plan_id
            user_subscription.stripe_customer_id = customer_id
            user_subscription.stripe_subscription_id = subscription_id
            user_subscription.status = SubscriptionStatus.ACTIVE
        else:
            # Create new subscription
            user_subscription = UserSubscription(
                user_id=user_id,
                plan_id=plan_id,
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                status=SubscriptionStatus.ACTIVE,
            )
            self.db.add(user_subscription)

        await self.db.commit()

        # Invalidate entitlements cache
        await invalidate_entitlements_cache(user_id, redis)

        # Create audit log
        audit_log = AuditLog(
            user_id=user_id,
            action="subscription_activated",
            metadata={"plan_id": plan_id_str, "stripe_subscription_id": subscription_id},
            success=True,
        )
        self.db.add(audit_log)
        await self.db.commit()

        logger.info(
            "subscription_activated",
            user_id=user_id_str,
            plan_id=plan_id_str,
            subscription_id=subscription_id,
        )

    async def _handle_subscription_updated(self, subscription: Dict[str, Any], redis) -> None:
        """Handle customer.subscription.updated event."""
        subscription_id = subscription["id"]

        result = await self.db.execute(
            select(UserSubscription)
            .where(UserSubscription.stripe_subscription_id == subscription_id)
            .limit(1)
        )
        user_subscription = result.scalar_one_or_none()

        if not user_subscription:
            logger.warning(
                "subscription_not_found_for_update", stripe_subscription_id=subscription_id
            )
            return

        # Update status
        status_map = {
            "active": SubscriptionStatus.ACTIVE,
            "past_due": SubscriptionStatus.PAST_DUE,
            "canceled": SubscriptionStatus.CANCELED,
            "trialing": SubscriptionStatus.TRIALING,
            "paused": SubscriptionStatus.PAUSED,
        }
        user_subscription.status = status_map.get(
            subscription["status"], SubscriptionStatus.ACTIVE
        )

        # Update period
        user_subscription.current_period_start = datetime.fromtimestamp(
            subscription["current_period_start"]
        )
        user_subscription.current_period_end = datetime.fromtimestamp(
            subscription["current_period_end"]
        )
        user_subscription.cancel_at_period_end = subscription.get("cancel_at_period_end", False)

        await self.db.commit()

        # Invalidate entitlements cache
        await invalidate_entitlements_cache(user_subscription.user_id, redis)

        logger.info(
            "subscription_updated",
            user_id=str(user_subscription.user_id),
            status=user_subscription.status.value,
        )

    async def _handle_subscription_deleted(self, subscription: Dict[str, Any], redis) -> None:
        """Handle customer.subscription.deleted event."""
        subscription_id = subscription["id"]

        result = await self.db.execute(
            select(UserSubscription)
            .where(UserSubscription.stripe_subscription_id == subscription_id)
            .limit(1)
        )
        user_subscription = result.scalar_one_or_none()

        if not user_subscription:
            logger.warning(
                "subscription_not_found_for_deletion", stripe_subscription_id=subscription_id
            )
            return

        # Downgrade to free plan
        free_plan_result = await self.db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.name == "free").limit(1)
        )
        free_plan = free_plan_result.scalar_one_or_none()

        if free_plan:
            user_subscription.plan_id = free_plan.id
            user_subscription.status = SubscriptionStatus.CANCELED
            await self.db.commit()

            # Invalidate entitlements cache
            await invalidate_entitlements_cache(user_subscription.user_id, redis)

            logger.info(
                "subscription_downgraded_to_free", user_id=str(user_subscription.user_id)
            )

    async def _handle_payment_failed(self, invoice: Dict[str, Any], redis) -> None:
        """Handle invoice.payment_failed event."""
        subscription_id = invoice.get("subscription")

        if not subscription_id:
            return

        result = await self.db.execute(
            select(UserSubscription)
            .where(UserSubscription.stripe_subscription_id == subscription_id)
            .limit(1)
        )
        user_subscription = result.scalar_one_or_none()

        if not user_subscription:
            return

        user_subscription.status = SubscriptionStatus.PAST_DUE
        await self.db.commit()

        # Invalidate entitlements cache
        await invalidate_entitlements_cache(user_subscription.user_id, redis)

        # Create audit log
        audit_log = AuditLog(
            user_id=user_subscription.user_id,
            action="payment_failed",
            metadata={
                "invoice_id": invoice["id"],
                "subscription_id": subscription_id,
                "amount_due": invoice.get("amount_due"),
            },
            success=False,
        )
        self.db.add(audit_log)
        await self.db.commit()

        logger.warning(
            "subscription_payment_failed",
            user_id=str(user_subscription.user_id),
            invoice_id=invoice["id"],
        )

    async def _handle_payment_succeeded(self, invoice: Dict[str, Any], redis) -> None:
        """Handle invoice.payment_succeeded event."""
        subscription_id = invoice.get("subscription")

        if not subscription_id:
            return

        result = await self.db.execute(
            select(UserSubscription)
            .where(UserSubscription.stripe_subscription_id == subscription_id)
            .limit(1)
        )
        user_subscription = result.scalar_one_or_none()

        if not user_subscription:
            return

        # Ensure subscription is active if payment succeeded
        if user_subscription.status != SubscriptionStatus.ACTIVE:
            user_subscription.status = SubscriptionStatus.ACTIVE
            await self.db.commit()

            # Invalidate entitlements cache
            await invalidate_entitlements_cache(user_subscription.user_id, redis)

        # Create audit log
        audit_log = AuditLog(
            user_id=user_subscription.user_id,
            action="payment_succeeded",
            metadata={
                "invoice_id": invoice["id"],
                "subscription_id": subscription_id,
                "amount_paid": invoice.get("amount_paid"),
            },
            success=True,
        )
        self.db.add(audit_log)
        await self.db.commit()

        logger.info(
            "subscription_payment_succeeded",
            user_id=str(user_subscription.user_id),
            invoice_id=invoice["id"],
        )

    async def _handle_customer_updated(self, customer: Dict[str, Any], redis) -> None:
        """Handle customer.updated event."""
        customer_id = customer["id"]

        result = await self.db.execute(
            select(UserSubscription)
            .where(UserSubscription.stripe_customer_id == customer_id)
            .limit(1)
        )
        user_subscription = result.scalar_one_or_none()

        if not user_subscription:
            logger.info("customer_updated_no_subscription_found", customer_id=customer_id)
            return

        # Update customer metadata if needed
        logger.info(
            "customer_updated",
            user_id=str(user_subscription.user_id),
            customer_id=customer_id,
        )

    async def cancel_subscription(self, user_id: UUID, redis) -> UserSubscription:
        """
        Cancel user subscription (keeps access until period end).

        Args:
            user_id: User ID
            redis: Redis client

        Returns:
            Updated UserSubscription

        Raises:
            ValueError: If no active subscription found
        """
        result = await self.db.execute(
            select(UserSubscription)
            .where(
                UserSubscription.user_id == user_id,
                UserSubscription.status == SubscriptionStatus.ACTIVE,
            )
            .limit(1)
        )
        user_subscription = result.scalar_one_or_none()

        if not user_subscription or not user_subscription.stripe_subscription_id:
            raise ValueError("No active subscription found")

        # Cancel at period end in Stripe
        try:
            stripe.Subscription.modify(
                user_subscription.stripe_subscription_id,
                cancel_at_period_end=True,
            )

            user_subscription.cancel_at_period_end = True
            await self.db.commit()

            # Invalidate entitlements cache
            await invalidate_entitlements_cache(user_id, redis)

            logger.info("subscription_canceled_at_period_end", user_id=str(user_id))

            return user_subscription

        except stripe.StripeError as e:
            logger.error("stripe_cancellation_failed", user_id=str(user_id), error=str(e))
            raise ValueError(f"Failed to cancel subscription: {str(e)}")

    async def get_billing_portal_url(self, user_id: UUID) -> str:
        """
        Get Stripe customer portal URL for self-service billing management.

        Args:
            user_id: User ID

        Returns:
            Portal URL

        Raises:
            ValueError: If no customer found or Stripe error
        """
        result = await self.db.execute(
            select(UserSubscription).where(UserSubscription.user_id == user_id).limit(1)
        )
        user_subscription = result.scalar_one_or_none()

        if not user_subscription or not user_subscription.stripe_customer_id:
            raise ValueError("No Stripe customer found")

        try:
            portal_session = stripe.billing_portal.Session.create(
                customer=user_subscription.stripe_customer_id,
                return_url="https://smartstockbot.app/dashboard/billing",
            )

            logger.info(
                "billing_portal_session_created",
                user_id=str(user_id),
                customer_id=user_subscription.stripe_customer_id,
            )

            return portal_session.url

        except stripe.StripeError as e:
            logger.error("billing_portal_failed", user_id=str(user_id), error=str(e))
            raise ValueError(f"Failed to create billing portal session: {str(e)}")
