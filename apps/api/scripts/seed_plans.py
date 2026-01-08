"""
Seed subscription plans and features into the database.

This script creates the Free and Pro plans with their associated features.
Run this after the billing migration to set up the initial subscription tiers.

Usage:
    python scripts/seed_plans.py
"""
import asyncio
import sys
from decimal import Decimal
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.billing import PlanFeature, SubscriptionPlan

logger = structlog.get_logger()


async def seed_plans():
    """Seed subscription plans and features."""
    async with SessionLocal() as db:
        try:
            # Check if plans already exist
            result = await db.execute(select(SubscriptionPlan))
            existing_plans = result.scalars().all()

            if existing_plans:
                logger.info("plans_already_exist", count=len(existing_plans))
                print(f"✓ Found {len(existing_plans)} existing plans. Skipping seed.")
                return

            logger.info("seeding_subscription_plans")
            print("Seeding subscription plans...")

            # ================================================================
            # Free Plan
            # ================================================================
            free_plan = SubscriptionPlan(
                name="free",
                display_name="Free Plan",
                description="Perfect for getting started with paper trading and delayed signals",
                price_monthly=Decimal("0.00"),
                price_yearly=Decimal("0.00"),
                stripe_price_id_monthly=None,  # No Stripe price for free plan
                stripe_price_id_yearly=None,
                is_active=True,
            )
            db.add(free_plan)
            await db.flush()  # Get the ID

            free_features = [
                PlanFeature(
                    plan_id=free_plan.id,
                    feature_key="live_trading_enabled",
                    feature_value="false",
                ),
                PlanFeature(
                    plan_id=free_plan.id,
                    feature_key="signal_delay_minutes",
                    feature_value="15",
                ),
                PlanFeature(
                    plan_id=free_plan.id,
                    feature_key="max_watchlist_symbols",
                    feature_value="5",
                ),
                PlanFeature(
                    plan_id=free_plan.id,
                    feature_key="daily_api_requests",
                    feature_value="100",
                ),
                PlanFeature(
                    plan_id=free_plan.id,
                    feature_key="realtime_alerts_enabled",
                    feature_value="false",
                ),
                PlanFeature(
                    plan_id=free_plan.id,
                    feature_key="backtest_enabled",
                    feature_value="false",
                ),
                PlanFeature(
                    plan_id=free_plan.id,
                    feature_key="paper_trading_enabled",
                    feature_value="true",
                ),
            ]
            for feature in free_features:
                db.add(feature)

            logger.info("free_plan_created", features_count=len(free_features))
            print(f"  ✓ Created Free plan with {len(free_features)} features")

            # ================================================================
            # Starter Plan ($19.99/mo)
            # ================================================================
            starter_plan = SubscriptionPlan(
                name="starter",
                display_name="Starter Plan",
                description="Real-time signals and basic trading features for beginners",
                price_monthly=Decimal("19.99"),
                price_yearly=Decimal("199.99"),  # ~17% discount for annual
                stripe_price_id_monthly="price_STARTER_MONTHLY",  # TODO: Replace with real Stripe price ID
                stripe_price_id_yearly="price_STARTER_YEARLY",  # TODO: Replace with real Stripe price ID
                is_active=True,
            )
            db.add(starter_plan)
            await db.flush()  # Get the ID

            starter_features = [
                PlanFeature(
                    plan_id=starter_plan.id,
                    feature_key="live_trading_enabled",
                    feature_value="false",
                ),
                PlanFeature(
                    plan_id=starter_plan.id,
                    feature_key="signal_delay_minutes",
                    feature_value="0",  # Real-time signals
                ),
                PlanFeature(
                    plan_id=starter_plan.id,
                    feature_key="max_watchlist_symbols",
                    feature_value="20",
                ),
                PlanFeature(
                    plan_id=starter_plan.id,
                    feature_key="daily_api_requests",
                    feature_value="1000",
                ),
                PlanFeature(
                    plan_id=starter_plan.id,
                    feature_key="realtime_alerts_enabled",
                    feature_value="true",
                ),
                PlanFeature(
                    plan_id=starter_plan.id,
                    feature_key="backtest_enabled",
                    feature_value="true",
                ),
                PlanFeature(
                    plan_id=starter_plan.id,
                    feature_key="paper_trading_enabled",
                    feature_value="true",
                ),
            ]
            for feature in starter_features:
                db.add(feature)

            logger.info("starter_plan_created", features_count=len(starter_features))
            print(f"  ✓ Created Starter plan with {len(starter_features)} features")

            # ================================================================
            # Pro Plan ($49.99/mo)
            # ================================================================
            # NOTE: Replace 'price_XXXXX' with actual Stripe price IDs from dashboard
            pro_plan = SubscriptionPlan(
                name="pro",
                display_name="Pro Plan",
                description="Full access with real-time signals, live trading, and premium features",
                price_monthly=Decimal("49.99"),
                price_yearly=Decimal("479.99"),  # ~20% discount for annual
                stripe_price_id_monthly="price_XXXXX",  # TODO: Replace with real Stripe price ID
                stripe_price_id_yearly="price_YYYYY",  # TODO: Replace with real Stripe price ID
                is_active=True,
            )
            db.add(pro_plan)
            await db.flush()  # Get the ID

            pro_features = [
                PlanFeature(
                    plan_id=pro_plan.id,
                    feature_key="live_trading_enabled",
                    feature_value="true",
                ),
                PlanFeature(
                    plan_id=pro_plan.id,
                    feature_key="signal_delay_minutes",
                    feature_value="0",
                ),
                PlanFeature(
                    plan_id=pro_plan.id,
                    feature_key="max_watchlist_symbols",
                    feature_value="999999",  # Unlimited
                ),
                PlanFeature(
                    plan_id=pro_plan.id,
                    feature_key="daily_api_requests",
                    feature_value="10000",
                ),
                PlanFeature(
                    plan_id=pro_plan.id,
                    feature_key="realtime_alerts_enabled",
                    feature_value="true",
                ),
                PlanFeature(
                    plan_id=pro_plan.id,
                    feature_key="backtest_enabled",
                    feature_value="true",
                ),
                PlanFeature(
                    plan_id=pro_plan.id,
                    feature_key="paper_trading_enabled",
                    feature_value="true",
                ),
                PlanFeature(
                    plan_id=pro_plan.id,
                    feature_key="priority_support",
                    feature_value="true",
                ),
                PlanFeature(
                    plan_id=pro_plan.id,
                    feature_key="custom_strategies_enabled",
                    feature_value="true",
                ),
            ]
            for feature in pro_features:
                db.add(feature)

            logger.info("pro_plan_created", features_count=len(pro_features))
            print(f"  ✓ Created Pro plan with {len(pro_features)} features")

            # Commit all changes
            await db.commit()

            logger.info("plans_seeded_successfully", total_plans=3)
            print("\n✓ Successfully seeded 3 subscription plans")
            print("\nPlans created:")
            print("  • Free Plan    ($0/mo) - Paper trading, delayed signals, basic features")
            print("  • Starter Plan ($19.99/mo or $199.99/yr) - Real-time signals, backtesting, paper trading")
            print("  • Pro Plan     ($49.99/mo or $479.99/yr) - Live trading, real-time signals, premium features")
            print("\nIMPORTANT: Update Stripe price IDs in the database for Starter and Pro plans:")
            print("  1. Create products in Stripe Dashboard")
            print("  2. Get price IDs for monthly and yearly billing")
            print("  3. Update Starter: UPDATE subscription_plans SET stripe_price_id_monthly='price_xxx', stripe_price_id_yearly='price_yyy' WHERE name='starter';")
            print("  4. Update Pro: UPDATE subscription_plans SET stripe_price_id_monthly='price_xxx', stripe_price_id_yearly='price_yyy' WHERE name='pro';")

        except Exception as e:
            logger.error("seed_plans_failed", error=str(e), exc_info=True)
            print(f"\n✗ Error seeding plans: {str(e)}")
            await db.rollback()
            raise


async def main():
    """Main entry point."""
    print("=" * 70)
    print("Subscription Plans Seed Script")
    print("=" * 70)
    print()

    try:
        await seed_plans()
        print("\n" + "=" * 70)
        print("Seed completed successfully!")
        print("=" * 70)
    except Exception as e:
        print("\n" + "=" * 70)
        print("Seed failed!")
        print("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
