"""initial auth models

Revision ID: 001
Revises:
Create Date: 2026-01-04 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create user_role enum type
    op.execute("CREATE TYPE user_role AS ENUM ('user', 'admin')")

    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('email_verified', sa.Boolean(), nullable=False),
        sa.Column('email_verification_token', sa.String(length=255), nullable=True),
        sa.Column('email_verification_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('mfa_enabled', sa.Boolean(), nullable=False),
        sa.Column('mfa_secret', sa.String(length=255), nullable=True),
        sa.Column('password_reset_token', sa.String(length=255), nullable=True),
        sa.Column('password_reset_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('phone_number', sa.String(length=20), nullable=True),
        sa.Column('role', postgresql.ENUM('user', 'admin', name='user_role', create_type=False), nullable=False),
        sa.Column('paper_trading_approved', sa.Boolean(), nullable=False),
        sa.Column('live_trading_approved', sa.Boolean(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_locked', sa.Boolean(), nullable=False),
        sa.Column('failed_login_attempts', sa.Integer(), nullable=False),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('preferences', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_email_verified', 'users', ['email', 'email_verified'])
    op.create_index('ix_users_deleted_at', 'users', ['deleted_at'])
    op.create_index('ix_users_created_at', 'users', ['created_at'])

    # Create sessions table
    op.create_table(
        'sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('refresh_token_hash', sa.String(length=255), nullable=False),
        sa.Column('device_info', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_used', sa.Boolean(), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_sessions_user_id', 'sessions', ['user_id'])
    op.create_index('ix_sessions_refresh_token_hash', 'sessions', ['refresh_token_hash'], unique=True)
    op.create_index('ix_sessions_user_id_is_revoked', 'sessions', ['user_id', 'is_revoked'])
    op.create_index('ix_sessions_expires_at', 'sessions', ['expires_at'])

    # Create mfa_backup_codes table
    op.create_table(
        'mfa_backup_codes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('code_hash', sa.String(length=255), nullable=False),
        sa.Column('is_used', sa.Boolean(), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_mfa_backup_codes_user_id', 'mfa_backup_codes', ['user_id'])
    op.create_index('ix_mfa_backup_codes_user_id_is_used', 'mfa_backup_codes', ['user_id', 'is_used'])

    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])
    op.create_index('ix_audit_logs_user_id_action', 'audit_logs', ['user_id', 'action'])
    op.create_index('ix_audit_logs_action_created_at', 'audit_logs', ['action', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_audit_logs_action_created_at', table_name='audit_logs')
    op.drop_index('ix_audit_logs_user_id_action', table_name='audit_logs')
    op.drop_index('ix_audit_logs_created_at', table_name='audit_logs')
    op.drop_index('ix_audit_logs_action', table_name='audit_logs')
    op.drop_index('ix_audit_logs_user_id', table_name='audit_logs')
    op.drop_table('audit_logs')

    op.drop_index('ix_mfa_backup_codes_user_id_is_used', table_name='mfa_backup_codes')
    op.drop_index('ix_mfa_backup_codes_user_id', table_name='mfa_backup_codes')
    op.drop_table('mfa_backup_codes')

    op.drop_index('ix_sessions_expires_at', table_name='sessions')
    op.drop_index('ix_sessions_user_id_is_revoked', table_name='sessions')
    op.drop_index('ix_sessions_refresh_token_hash', table_name='sessions')
    op.drop_index('ix_sessions_user_id', table_name='sessions')
    op.drop_table('sessions')

    op.drop_index('ix_users_created_at', table_name='users')
    op.drop_index('ix_users_deleted_at', table_name='users')
    op.drop_index('ix_users_email_verified', table_name='users')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')

    op.execute("DROP TYPE user_role")
