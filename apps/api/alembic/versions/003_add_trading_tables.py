"""add trading tables

Revision ID: 003
Revises: 002
Create Date: 2026-01-08 14:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create trading_mode enum type
    op.execute("CREATE TYPE trading_mode AS ENUM ('paper', 'live')")

    # Create order_side enum type
    op.execute("CREATE TYPE order_side AS ENUM ('buy', 'sell')")

    # Create order_type enum type
    op.execute("CREATE TYPE order_type AS ENUM ('market', 'limit', 'stop', 'stop_limit')")

    # Create order_status enum type
    op.execute("CREATE TYPE order_status AS ENUM ('pending', 'filled', 'partially_filled', 'canceled', 'rejected', 'expired')")

    # Create orders table
    op.create_table(
        'orders',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('mode', postgresql.ENUM('paper', 'live', name='trading_mode', create_type=False), nullable=False),
        sa.Column('symbol', sa.String(length=10), nullable=False),
        sa.Column('side', postgresql.ENUM('buy', 'sell', name='order_side', create_type=False), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('order_type', postgresql.ENUM('market', 'limit', 'stop', 'stop_limit', name='order_type', create_type=False), nullable=False),
        sa.Column('limit_price', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('stop_price', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('status', postgresql.ENUM('pending', 'filled', 'partially_filled', 'canceled', 'rejected', 'expired', name='order_status', create_type=False), nullable=False),
        sa.Column('filled_quantity', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('filled_avg_price', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('broker_order_id', sa.String(length=255), nullable=True),
        sa.Column('broker_name', sa.String(length=50), nullable=False, server_default='alpaca'),
        sa.Column('time_in_force', sa.String(length=10), nullable=False, server_default='gtc'),
        sa.Column('extended_hours', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('filled_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_orders_user_id', 'orders', ['user_id'])
    op.create_index('ix_orders_mode', 'orders', ['mode'])
    op.create_index('ix_orders_symbol', 'orders', ['symbol'])
    op.create_index('ix_orders_status', 'orders', ['status'])
    op.create_index('ix_orders_broker_order_id', 'orders', ['broker_order_id'], unique=True)
    op.create_index('ix_orders_created_at', 'orders', ['created_at'])
    op.create_index('ix_orders_user_mode_status', 'orders', ['user_id', 'mode', 'status'])

    # Create positions table
    op.create_table(
        'positions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('mode', postgresql.ENUM('paper', 'live', name='trading_mode', create_type=False), nullable=False),
        sa.Column('symbol', sa.String(length=10), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('avg_entry_price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('current_price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('market_value', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('cost_basis', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('unrealized_pl', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('unrealized_pl_percent', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('broker_name', sa.String(length=50), nullable=False, server_default='alpaca'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'mode', 'symbol', 'broker_name', name='uq_positions_user_mode_symbol_broker')
    )
    op.create_index('ix_positions_user_id', 'positions', ['user_id'])
    op.create_index('ix_positions_mode', 'positions', ['mode'])
    op.create_index('ix_positions_symbol', 'positions', ['symbol'])
    op.create_index('ix_positions_user_mode', 'positions', ['user_id', 'mode'])

    # Create account_snapshots table (track portfolio value over time)
    op.create_table(
        'account_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('mode', postgresql.ENUM('paper', 'live', name='trading_mode', create_type=False), nullable=False),
        sa.Column('equity', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('cash', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('buying_power', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('portfolio_value', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('snapshot_time', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'mode', 'snapshot_date', name='uq_account_snapshots_user_mode_date')
    )
    op.create_index('ix_account_snapshots_user_id', 'account_snapshots', ['user_id'])
    op.create_index('ix_account_snapshots_mode', 'account_snapshots', ['mode'])
    op.create_index('ix_account_snapshots_snapshot_date', 'account_snapshots', ['snapshot_date'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_account_snapshots_snapshot_date', table_name='account_snapshots')
    op.drop_index('ix_account_snapshots_mode', table_name='account_snapshots')
    op.drop_index('ix_account_snapshots_user_id', table_name='account_snapshots')

    op.drop_index('ix_positions_user_mode', table_name='positions')
    op.drop_index('ix_positions_symbol', table_name='positions')
    op.drop_index('ix_positions_mode', table_name='positions')
    op.drop_index('ix_positions_user_id', table_name='positions')

    op.drop_index('ix_orders_user_mode_status', table_name='orders')
    op.drop_index('ix_orders_created_at', table_name='orders')
    op.drop_index('ix_orders_broker_order_id', table_name='orders')
    op.drop_index('ix_orders_status', table_name='orders')
    op.drop_index('ix_orders_symbol', table_name='orders')
    op.drop_index('ix_orders_mode', table_name='orders')
    op.drop_index('ix_orders_user_id', table_name='orders')

    # Drop tables
    op.drop_table('account_snapshots')
    op.drop_table('positions')
    op.drop_table('orders')

    # Drop enum types
    op.execute("DROP TYPE order_status")
    op.execute("DROP TYPE order_type")
    op.execute("DROP TYPE order_side")
    op.execute("DROP TYPE trading_mode")
