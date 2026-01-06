"""
Privacy and data management service for GDPR compliance.
"""
from datetime import datetime
from typing import Any, Dict
from uuid import UUID

import structlog
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import AuditLog, MFABackupCode, Session, User

logger = structlog.get_logger()


class PrivacyService:
    """Privacy service for data export, deletion, and consent management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def export_user_data(self, user_id: UUID) -> Dict[str, Any]:
        """
        Export all user data for GDPR compliance (Right to Access).

        Returns a comprehensive JSON export of:
        - User profile (excluding password hash and sensitive tokens)
        - Active sessions
        - MFA status (excluding secrets)
        - Audit logs
        - Preferences and consent settings

        Args:
            user_id: UUID of the user requesting the export

        Returns:
            Dict containing all user data

        Raises:
            ValueError: If user not found
        """
        # Fetch user
        result = await self.db.execute(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found or has been deleted")

        # Fetch active sessions
        sessions_result = await self.db.execute(
            select(Session).where(
                Session.user_id == user_id,
                Session.is_revoked == False  # noqa: E712
            ).order_by(Session.created_at.desc())
        )
        sessions = sessions_result.scalars().all()

        # Fetch MFA backup codes (only count, not actual codes)
        backup_codes_result = await self.db.execute(
            select(MFABackupCode).where(
                MFABackupCode.user_id == user_id,
                MFABackupCode.is_used == False  # noqa: E712
            )
        )
        unused_backup_codes_count = len(backup_codes_result.scalars().all())

        # Fetch audit logs
        audit_logs_result = await self.db.execute(
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.created_at.desc())
            .limit(1000)  # Limit to last 1000 entries
        )
        audit_logs = audit_logs_result.scalars().all()

        # Build export data
        export_data = {
            "export_metadata": {
                "exported_at": datetime.utcnow().isoformat(),
                "user_id": str(user.id),
                "format_version": "1.0",
            },
            "profile": {
                "email": user.email,
                "full_name": user.full_name,
                "phone_number": user.phone_number,
                "email_verified": user.email_verified,
                "role": user.role.value,
                "is_active": user.is_active,
                "is_locked": user.is_locked,
                "created_at": user.created_at.isoformat(),
                "updated_at": user.updated_at.isoformat(),
                "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            },
            "security": {
                "mfa_enabled": user.mfa_enabled,
                "unused_backup_codes_count": unused_backup_codes_count,
                "failed_login_attempts": user.failed_login_attempts,
                "locked_until": user.locked_until.isoformat() if user.locked_until else None,
            },
            "permissions": {
                "paper_trading_approved": user.paper_trading_approved,
                "live_trading_approved": user.live_trading_approved,
            },
            "preferences": user.preferences,
            "sessions": [
                {
                    "id": str(session.id),
                    "device_info": session.device_info,
                    "created_at": session.created_at.isoformat(),
                    "last_used_at": session.last_used_at.isoformat(),
                    "expires_at": session.expires_at.isoformat(),
                }
                for session in sessions
            ],
            "audit_logs": [
                {
                    "action": log.action,
                    "success": log.success,
                    "ip_address": log.ip_address,
                    "user_agent": log.user_agent,
                    "metadata": log.action_metadata,
                    "error_message": log.error_message,
                    "created_at": log.created_at.isoformat(),
                }
                for log in audit_logs
            ],
        }

        # Log the data export action
        audit_log = AuditLog(
            user_id=user_id,
            action="data_export",
            ip_address=None,  # Will be set by the endpoint
            user_agent=None,  # Will be set by the endpoint
            success=True,
        )
        self.db.add(audit_log)
        await self.db.commit()

        logger.info(
            "user_data_exported",
            user_id=str(user_id),
            sessions_count=len(sessions),
            audit_logs_count=len(audit_logs),
        )

        return export_data

    async def soft_delete_account(self, user_id: UUID, client_info: dict) -> None:
        """
        Soft delete user account for GDPR compliance (Right to Erasure).

        Performs the following actions:
        - Sets deleted_at timestamp on user account
        - Revokes all active sessions
        - Anonymizes audit logs (replaces PII with anonymized values)
        - Creates audit log entry for deletion

        The user record is preserved for audit/compliance purposes but
        marked as deleted. The account cannot be recovered.

        Args:
            user_id: UUID of the user to delete
            client_info: Client IP and user agent for audit log

        Raises:
            ValueError: If user not found
        """
        # Fetch user
        result = await self.db.execute(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found or already deleted")

        # Mark user as deleted
        user.deleted_at = datetime.utcnow()
        user.email = f"deleted_{user_id}@deleted.local"  # Anonymize email
        user.full_name = None  # Clear PII
        user.phone_number = None  # Clear PII
        user.email_verification_token = None
        user.password_reset_token = None
        user.mfa_secret = None
        user.preferences = {}

        # Revoke all sessions
        await self.db.execute(
            update(Session)
            .where(Session.user_id == user_id, Session.is_revoked == False)  # noqa: E712
            .values(is_revoked=True, revoked_at=datetime.utcnow())
        )

        # Delete MFA backup codes
        await self.db.execute(
            delete(MFABackupCode).where(MFABackupCode.user_id == user_id)
        )

        # Anonymize audit logs (preserve for compliance but remove PII)
        await self.db.execute(
            update(AuditLog)
            .where(AuditLog.user_id == user_id)
            .values(
                ip_address="0.0.0.0",  # Anonymize IP
                user_agent="anonymized",  # Anonymize user agent
            )
        )

        # Create audit log for deletion
        audit_log = AuditLog(
            user_id=user_id,
            action="account_deleted",
            ip_address=client_info.get("ip_address"),
            user_agent=client_info.get("user_agent"),
            success=True,
        )
        self.db.add(audit_log)

        await self.db.commit()

        logger.info(
            "user_account_soft_deleted",
            user_id=str(user_id),
        )

    async def hard_delete_account(self, user_id: UUID, client_info: dict) -> None:
        """
        Permanently delete user account and all related data (ADMIN ONLY).

        WARNING: This operation is irreversible and deletes ALL user data
        including audit logs. Use only when legally required.

        Deletes:
        - All audit logs
        - All sessions
        - All MFA backup codes
        - User account

        Args:
            user_id: UUID of the user to permanently delete
            client_info: Client IP and user agent for audit log

        Raises:
            ValueError: If user not found
        """
        # Fetch user (including soft-deleted users)
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found")

        # Create audit log BEFORE deletion (this will also be deleted)
        audit_log = AuditLog(
            user_id=user_id,
            action="account_hard_deleted",
            ip_address=client_info.get("ip_address"),
            user_agent=client_info.get("user_agent"),
            success=True,
        )
        self.db.add(audit_log)
        await self.db.flush()  # Ensure it's written before cascading deletes

        logger.warning(
            "user_account_hard_delete_initiated",
            user_id=str(user_id),
            email=user.email,
        )

        # Delete all related data
        await self.db.execute(delete(AuditLog).where(AuditLog.user_id == user_id))
        await self.db.execute(delete(Session).where(Session.user_id == user_id))
        await self.db.execute(delete(MFABackupCode).where(MFABackupCode.user_id == user_id))

        # Delete user
        await self.db.execute(delete(User).where(User.id == user_id))

        await self.db.commit()

        logger.warning(
            "user_account_hard_deleted",
            user_id=str(user_id),
        )

    async def get_user_preferences(self, user_id: UUID) -> Dict[str, Any]:
        """
        Get user privacy preferences.

        Args:
            user_id: UUID of the user

        Returns:
            Dict containing user preferences

        Raises:
            ValueError: If user not found
        """
        result = await self.db.execute(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found or has been deleted")

        # Return preferences with defaults
        default_preferences = {
            "analytics_consent": False,
            "email_notifications": True,
            "trade_confirmations": True,
            "marketing_emails": False,
            "theme": "light",
        }

        # Merge user preferences with defaults
        preferences = {**default_preferences, **user.preferences}

        logger.info(
            "user_preferences_retrieved",
            user_id=str(user_id),
        )

        return preferences

    async def update_user_preferences(
        self, user_id: UUID, preferences: Dict[str, Any], client_info: dict
    ) -> Dict[str, Any]:
        """
        Update user privacy preferences.

        Args:
            user_id: UUID of the user
            preferences: Dictionary of preference updates
            client_info: Client IP and user agent for audit log

        Returns:
            Dict containing updated preferences

        Raises:
            ValueError: If user not found
        """
        result = await self.db.execute(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found or has been deleted")

        # Get current preferences
        current_preferences = user.preferences or {}

        # Update with new values (merge)
        updated_preferences = {**current_preferences, **preferences}

        # Update user
        user.preferences = updated_preferences
        await self.db.commit()
        await self.db.refresh(user)

        # Create audit log
        audit_log = AuditLog(
            user_id=user_id,
            action="preferences_updated",
            ip_address=client_info.get("ip_address"),
            user_agent=client_info.get("user_agent"),
            action_metadata={"updated_fields": list(preferences.keys())},
            success=True,
        )
        self.db.add(audit_log)
        await self.db.commit()

        logger.info(
            "user_preferences_updated",
            user_id=str(user_id),
            updated_fields=list(preferences.keys()),
        )

        # Return preferences with defaults (same as get_user_preferences)
        default_preferences = {
            "analytics_consent": False,
            "email_notifications": True,
            "trade_confirmations": True,
            "marketing_emails": False,
            "theme": "light",
        }
        return {**default_preferences, **user.preferences}
