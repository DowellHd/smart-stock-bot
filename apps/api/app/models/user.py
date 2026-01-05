"""
User and authentication related database models.
"""
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String, Text, Index, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
import enum

from app.core.database import Base


class UserRole(str, enum.Enum):
    """User role enumeration."""
    USER = "user"
    ADMIN = "admin"


class User(Base):
    """User model with authentication and profile information."""

    __tablename__ = "users"

    # Primary key
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Authentication
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verification_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email_verification_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # MFA
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mfa_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Encrypted TOTP secret

    # Password reset
    password_reset_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    password_reset_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Profile
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Role and permissions
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole, name="user_role", create_type=True),
        default=UserRole.USER,
        nullable=False,
    )

    # Trading permissions
    paper_trading_approved: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    live_trading_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Account status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_login_attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Privacy and consent
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    # preferences structure:
    # {
    #   "analytics_consent": bool,
    #   "email_notifications": bool,
    #   "trade_confirmations": bool,
    #   "marketing_emails": bool,
    #   "theme": "light" | "dark",
    # }

    # Soft delete
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Indexes
    __table_args__ = (
        Index("ix_users_email_verified", "email", "email_verified"),
        Index("ix_users_deleted_at", "deleted_at"),
        Index("ix_users_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"


class Session(Base):
    """Session model for refresh token management."""

    __tablename__ = "sessions"

    # Primary key
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # User reference
    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    # Token (hashed)
    refresh_token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)

    # Device information
    device_info: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    # device_info structure:
    # {
    #   "user_agent": str,
    #   "ip_address": str,
    #   "device_name": str (optional),
    #   "location": str (optional),
    # }

    # Session state
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Activity tracking
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    # Token rotation detection
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Indexes
    __table_args__ = (
        Index("ix_sessions_user_id_is_revoked", "user_id", "is_revoked"),
        Index("ix_sessions_expires_at", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<Session {self.id} for user {self.user_id}>"


class MFABackupCode(Base):
    """MFA backup codes for account recovery."""

    __tablename__ = "mfa_backup_codes"

    # Primary key
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # User reference
    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    # Backup code (hashed)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Usage tracking
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    # Indexes
    __table_args__ = (
        Index("ix_mfa_backup_codes_user_id_is_used", "user_id", "is_used"),
    )

    def __repr__(self) -> str:
        return f"<MFABackupCode for user {self.user_id}>"


class AuditLog(Base):
    """Audit log for security-sensitive actions."""

    __tablename__ = "audit_logs"

    # Primary key
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # User reference (nullable for anonymous actions)
    user_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    # Action details
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # Common actions: login, logout, login_failed, mfa_enabled, mfa_disabled,
    #                 password_changed, email_changed, session_revoked,
    #                 trade_placed, transfer_initiated, etc.

    # Request information
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # IPv6 max length
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Additional metadata
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    # metadata can include action-specific details

    # Result
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True
    )

    # Indexes
    __table_args__ = (
        Index("ix_audit_logs_user_id_action", "user_id", "action"),
        Index("ix_audit_logs_action_created_at", "action", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by user {self.user_id}>"
