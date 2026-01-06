"""
Privacy and data management service for GDPR compliance.
"""
from datetime import datetime
from typing import Any, Dict
from uuid import UUID

import structlog
from sqlalchemy import select
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
