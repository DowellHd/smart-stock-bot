"""add billing tables

Revision ID: 002
Revises: 001
Create Date: 2026-01-06 15:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create subscription_status enum type
    op.execute("CREATE TYPE subscription_status AS ENUM ('active', 'canceled', 'past_due', 'trialing', 'paused')")

    # Create subscription_plans table
    op.create_table(
        'subscription_plans',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price_monthly', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('price_yearly', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('stripe_price_id_monthly', sa.String(length=255), nullable=True),
        sa.Column('stripe_price_id_yearly', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_subscription_plans_name', 'subscription_plans', ['name'], unique=True)
    op.create_index('ix_subscription_plans_is_active', 'subscription_plans', ['is_active'])

    # Create plan_features table
    op.create_table(
        'plan_features',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('feature_key', sa.String(length=100), nullable=False),
        sa.Column('feature_value', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['plan_id'], ['subscription_plans.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('plan_id', 'feature_key', name='uq_plan_features_plan_key')
    )
    op.create_index('ix_plan_features_plan_id', 'plan_features', ['plan_id'])
    op.create_index('ix_plan_features_feature_key', 'plan_features', ['feature_key'])

    # Create user_subscriptions table
    op.create_table(
        'user_subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('stripe_customer_id', sa.String(length=255), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(length=255), nullable=True),
        sa.Column('status', postgresql.ENUM('active', 'canceled', 'past_due', 'trialing', 'paused', name='subscription_status', create_type=False), nullable=False),
        sa.Column('current_period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('trial_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['plan_id'], ['subscription_plans.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_user_subscriptions_user_id', 'user_subscriptions', ['user_id'], unique=True)
    op.create_index('ix_user_subscriptions_stripe_customer_id', 'user_subscriptions', ['stripe_customer_id'], unique=True)
    op.create_index('ix_user_subscriptions_stripe_subscription_id', 'user_subscriptions', ['stripe_subscription_id'], unique=True)
    op.create_index('ix_user_subscriptions_status', 'user_subscriptions', ['status'])

    # Create usage_metrics table
    op.create_table(
        'usage_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('metric_type', sa.String(length=100), nullable=False),
        sa.Column('metric_value', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('metric_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_usage_metrics_user_id', 'usage_metrics', ['user_id'])
    op.create_index('ix_usage_metrics_metric_type', 'usage_metrics', ['metric_type'])
    op.create_index('ix_usage_metrics_created_at', 'usage_metrics', ['created_at'])
    op.create_index('ix_usage_metrics_user_type_date', 'usage_metrics', ['user_id', 'metric_type', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_usage_metrics_user_type_date', table_name='usage_metrics')
    op.drop_index('ix_usage_metrics_created_at', table_name='usage_metrics')
    op.drop_index('ix_usage_metrics_metric_type', table_name='usage_metrics')
    op.drop_index('ix_usage_metrics_user_id', table_name='usage_metrics')
    op.drop_table('usage_metrics')

    op.drop_index('ix_user_subscriptions_status', table_name='user_subscriptions')
    op.drop_index('ix_user_subscriptions_stripe_subscription_id', table_name='user_subscriptions')
    op.drop_index('ix_user_subscriptions_stripe_customer_id', table_name='user_subscriptions')
    op.drop_index('ix_user_subscriptions_user_id', table_name='user_subscriptions')
    op.drop_table('user_subscriptions')

    op.drop_index('ix_plan_features_feature_key', table_name='plan_features')
    op.drop_index('ix_plan_features_plan_id', table_name='plan_features')
    op.drop_table('plan_features')

    op.drop_index('ix_subscription_plans_is_active', table_name='subscription_plans')
    op.drop_index('ix_subscription_plans_name', table_name='subscription_plans')
    op.drop_table('subscription_plans')

    op.execute("DROP TYPE subscription_status")
