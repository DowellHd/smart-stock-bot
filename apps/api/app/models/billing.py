"""
Billing and subscription models.
"""
import enum
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SubscriptionStatus(str, enum.Enum):
    """Subscription status enum."""

    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"
    PAUSED = "paused"


class SubscriptionPlan(Base):
    """
    Subscription plan definition (Free, Pro, etc.).

    Static tier definitions that define available plans.
    """

    __tablename__ = "subscription_plans"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price_monthly: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    price_yearly: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    stripe_price_id_monthly: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    stripe_price_id_yearly: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    features: Mapped[List["PlanFeature"]] = relationship(
        "PlanFeature", back_populates="plan", cascade="all, delete-orphan"
    )
    subscriptions: Mapped[List["UserSubscription"]] = relationship(
        "UserSubscription", back_populates="plan"
    )

    def __repr__(self) -> str:
        return f"<SubscriptionPlan(name={self.name}, price=${self.price_monthly}/mo)>"


class PlanFeature(Base):
    """
    Features included in each subscription plan.

    Stores feature flags and limits per plan.
    """

    __tablename__ = "plan_features"
    __table_args__ = (UniqueConstraint("plan_id", "feature_key", name="uq_plan_features_plan_key"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    plan_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("subscription_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    feature_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    feature_value: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # Relationships
    plan: Mapped["SubscriptionPlan"] = relationship("SubscriptionPlan", back_populates="features")

    def __repr__(self) -> str:
        return f"<PlanFeature(plan_id={self.plan_id}, key={self.feature_key})>"


class UserSubscription(Base):
    """
    User's current subscription state.

    Tracks user's subscription to a plan, Stripe details, and status.
    """

    __tablename__ = "user_subscriptions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    plan_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("subscription_plans.id"), nullable=False
    )
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        SQLEnum(SubscriptionStatus), nullable=False, index=True
    )
    current_period_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_period_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    trial_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    plan: Mapped["SubscriptionPlan"] = relationship("SubscriptionPlan", back_populates="subscriptions")

    def __repr__(self) -> str:
        return f"<UserSubscription(user_id={self.user_id}, plan={self.plan.name if self.plan else None}, status={self.status})>"


class UsageMetric(Base):
    """
    Track API usage and actions for quota enforcement.

    Used for rate limiting and usage analytics.
    """

    __tablename__ = "usage_metrics"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    metric_value: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    metric_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True
    )

    def __repr__(self) -> str:
        return f"<UsageMetric(user_id={self.user_id}, type={self.metric_type}, value={self.metric_value})>"
