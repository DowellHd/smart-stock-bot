"""
Entitlements system for subscription-based feature access control.

This module provides the Entitlements class and dependency injection
for enforcing plan-based access control across the API.
"""
import json
from typing import Any, Dict, Optional
from uuid import UUID

import structlog
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.redis import get_redis
from app.models.billing import PlanFeature, SubscriptionPlan, UserSubscription
from app.models.user import User

logger = structlog.get_logger()


class Entitlements:
    """
    Entitlements object representing user's subscription-based permissions.

    Provides methods to check feature access and retrieve feature values.
    """

    def __init__(self, plan_name: str, features: Dict[str, Any], user_id: str):
        """
        Initialize entitlements.

        Args:
            plan_name: Name of the user's subscription plan
            features: Dictionary of feature_key -> feature_value
            user_id: User ID string
        """
        self.plan_name = plan_name
        self.features = features
        self.user_id = user_id

    def require_feature(self, feature_key: str, expected_value: Any = True) -> None:
        """
        Require a feature to have a specific value, raise 403 if not met.

        Args:
            feature_key: Feature to check (e.g., 'live_trading_enabled')
            expected_value: Expected value for the feature

        Raises:
            HTTPException: 403 if feature requirement not met
        """
        actual_value = self.get_feature_value(feature_key)

        # Convert string values to appropriate types for comparison
        if isinstance(expected_value, bool):
            actual_value = str(actual_value).lower() == "true" if isinstance(actual_value, str) else bool(actual_value)

        if actual_value != expected_value:
            logger.warning(
                "feature_access_denied",
                user_id=self.user_id,
                plan=self.plan_name,
                feature_key=feature_key,
                expected=expected_value,
                actual=actual_value,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Feature '{feature_key}' not available on {self.plan_name} plan. Upgrade to access this feature.",
            )

    def get_feature_value(self, feature_key: str, default: Any = None) -> Any:
        """
        Get feature value from entitlements.

        Args:
            feature_key: Feature to retrieve
            default: Default value if feature not found

        Returns:
            Feature value (parsed from JSON if needed) or default
        """
        raw_value = self.features.get(feature_key, default)

        if raw_value is None:
            return default

        # Try to parse as JSON if it's a string
        if isinstance(raw_value, str):
            try:
                return json.loads(raw_value)
            except (json.JSONDecodeError, ValueError):
                return raw_value

        return raw_value

    def get_limit(self, limit_key: str, default: int = 0) -> int:
        """
        Get numeric limit from entitlements.

        Args:
            limit_key: Limit to retrieve (e.g., 'daily_api_requests')
            default: Default limit if not found

        Returns:
            Limit as integer
        """
        value = self.get_feature_value(limit_key, default)
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def has_feature(self, feature_key: str) -> bool:
        """
        Check if a feature is enabled (boolean check).

        Args:
            feature_key: Feature to check

        Returns:
            True if feature is enabled, False otherwise
        """
        value = self.get_feature_value(feature_key, False)
        if isinstance(value, str):
            return value.lower() == "true"
        return bool(value)


async def get_entitlements(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis),
) -> Entitlements:
    """
    Dependency to get user entitlements with caching.

    Flow:
    1. Check Redis cache for user entitlements
    2. If not cached, query database for user subscription and plan features
    3. If no active subscription, assign free plan
    4. Cache result in Redis (TTL: 5 minutes)
    5. Return Entitlements object

    Args:
        current_user: Current authenticated user
        db: Database session
        redis: Redis client

    Returns:
        Entitlements object for the user

    Raises:
        HTTPException: 500 if unable to load entitlements
    """
    cache_key = f"entitlements:{current_user.id}"

    try:
        # Try to get from cache
        cached = await redis.get(cache_key)
        if cached:
            cached_data = json.loads(cached)
            logger.debug(
                "entitlements_cache_hit",
                user_id=str(current_user.id),
                plan=cached_data.get("plan_name"),
            )
            return Entitlements(
                plan_name=cached_data["plan_name"],
                features=cached_data["features"],
                user_id=str(current_user.id),
            )

        # Cache miss - load from database
        logger.debug("entitlements_cache_miss", user_id=str(current_user.id))

        # Query user subscription with plan and features
        result = await db.execute(
            select(UserSubscription)
            .where(
                UserSubscription.user_id == current_user.id,
                UserSubscription.status == "active",
            )
            .limit(1)
        )
        subscription = result.scalar_one_or_none()

        if subscription:
            # Load plan features
            plan_id = subscription.plan_id
            plan_name = subscription.plan.name

            features_result = await db.execute(
                select(PlanFeature).where(PlanFeature.plan_id == plan_id)
            )
            features = features_result.scalars().all()

            # Build features dictionary
            features_dict = {feature.feature_key: feature.feature_value for feature in features}

            logger.info(
                "entitlements_loaded_from_subscription",
                user_id=str(current_user.id),
                plan=plan_name,
                features_count=len(features_dict),
            )
        else:
            # No active subscription - use free plan defaults
            logger.info("no_active_subscription_defaulting_to_free", user_id=str(current_user.id))

            # Try to load free plan from database
            free_plan_result = await db.execute(
                select(SubscriptionPlan).where(SubscriptionPlan.name == "free").limit(1)
            )
            free_plan = free_plan_result.scalar_one_or_none()

            if free_plan:
                plan_name = "free"
                features_result = await db.execute(
                    select(PlanFeature).where(PlanFeature.plan_id == free_plan.id)
                )
                features = features_result.scalars().all()
                features_dict = {feature.feature_key: feature.feature_value for feature in features}
            else:
                # Free plan not in DB - use hardcoded defaults
                logger.warning("free_plan_not_found_using_hardcoded_defaults")
                plan_name = "free"
                features_dict = {
                    "live_trading_enabled": "false",
                    "signal_delay_minutes": "15",
                    "max_watchlist_symbols": "5",
                    "daily_api_requests": "100",
                    "realtime_alerts_enabled": "false",
                }

        # Cache for 5 minutes
        cache_data = {"plan_name": plan_name, "features": features_dict}
        await redis.setex(cache_key, 300, json.dumps(cache_data))

        logger.info(
            "entitlements_cached",
            user_id=str(current_user.id),
            plan=plan_name,
            ttl_seconds=300,
        )

        return Entitlements(
            plan_name=plan_name, features=features_dict, user_id=str(current_user.id)
        )

    except Exception as e:
        logger.error(
            "failed_to_load_entitlements",
            user_id=str(current_user.id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load user entitlements",
        )


async def invalidate_entitlements_cache(user_id: UUID, redis) -> None:
    """
    Invalidate cached entitlements for a user.

    Call this after subscription changes to force reload on next request.

    Args:
        user_id: User ID to invalidate cache for
        redis: Redis client
    """
    cache_key = f"entitlements:{user_id}"
    await redis.delete(cache_key)
    logger.info("entitlements_cache_invalidated", user_id=str(user_id))
