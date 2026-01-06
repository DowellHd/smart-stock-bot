"""
Pydantic schemas for billing and subscriptions.
"""
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.billing import SubscriptionStatus


# ============================================================================
# Subscription Plan Schemas
# ============================================================================


class PlanFeatureSchema(BaseModel):
    """Plan feature schema."""

    feature_key: str
    feature_value: str

    model_config = {"from_attributes": True}


class SubscriptionPlanSchema(BaseModel):
    """Subscription plan schema."""

    id: UUID
    name: str
    display_name: str
    description: Optional[str] = None
    price_monthly: Decimal
    price_yearly: Optional[Decimal] = None
    is_active: bool
    features: List[PlanFeatureSchema] = []

    model_config = {"from_attributes": True}


class SubscriptionPlanListResponse(BaseModel):
    """Response for listing subscription plans."""

    plans: List[SubscriptionPlanSchema]


# ============================================================================
# User Subscription Schemas
# ============================================================================


class UserSubscriptionSchema(BaseModel):
    """User subscription schema."""

    id: UUID
    user_id: UUID
    plan: SubscriptionPlanSchema
    status: SubscriptionStatus
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool
    trial_end: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SubscriptionResponse(BaseModel):
    """Response for subscription details."""

    subscription: Optional[UserSubscriptionSchema] = None
    message: Optional[str] = None


# ============================================================================
# Checkout & Billing Actions
# ============================================================================


class CheckoutRequest(BaseModel):
    """Request to create a checkout session."""

    plan_name: str = Field(..., description="Plan name (e.g., 'pro')")
    billing_cycle: str = Field(..., description="Billing cycle: 'monthly' or 'yearly'")
    success_url: Optional[str] = Field(
        None, description="URL to redirect after successful checkout"
    )
    cancel_url: Optional[str] = Field(None, description="URL to redirect after canceled checkout")


class CheckoutResponse(BaseModel):
    """Response with checkout session URL."""

    checkout_url: str
    session_id: str


class BillingPortalResponse(BaseModel):
    """Response with billing portal URL."""

    portal_url: str


class CancelSubscriptionResponse(BaseModel):
    """Response for subscription cancellation."""

    message: str
    subscription: UserSubscriptionSchema


# ============================================================================
# Webhook Schemas
# ============================================================================


class StripeWebhookEvent(BaseModel):
    """Stripe webhook event payload."""

    id: str
    type: str
    data: Dict[str, Any]
    created: int


# ============================================================================
# Usage Metrics Schemas
# ============================================================================


class UsageMetricSchema(BaseModel):
    """Usage metric schema."""

    id: UUID
    user_id: UUID
    metric_type: str
    metric_value: int
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UsageStatsResponse(BaseModel):
    """Response for usage statistics."""

    user_id: UUID
    period_start: datetime
    period_end: datetime
    metrics: Dict[str, int]
    plan_limits: Dict[str, Any]
