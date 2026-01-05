"""
Authentication service with business logic for user registration, login, MFA, etc.
"""
from datetime import datetime, timedelta
from typing import Optional, Tuple
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decrypt_field,
    encrypt_field,
    generate_backup_codes,
    generate_secure_token,
    generate_totp_secret,
    generate_totp_uri,
    hash_password,
    hash_token,
    verify_password,
    verify_totp,
)
from app.models.user import AuditLog, MFABackupCode, Session, User
from app.schemas.auth import SignupRequest
from app.services.email import email_service

logger = structlog.get_logger()

# Account lockout settings
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 30


class AuthService:
    """Authentication service for user management and auth operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(
        self,
        signup_data: SignupRequest,
        client_info: dict,
    ) -> User:
        """
        Create a new user account.

        Args:
            signup_data: Signup request data
            client_info: Client IP and user agent

        Returns:
            Created user

        Raises:
            ValueError: If email already exists
        """
        # Check if email exists
        result = await self.db.execute(
            select(User).where(User.email == signup_data.email, User.deleted_at.is_(None))
        )
        if result.scalar_one_or_none():
            raise ValueError("Email already registered")

        # Hash password
        password_hash = hash_password(signup_data.password)

        # Generate email verification token
        verification_token = generate_secure_token()

        # Create user
        user = User(
            email=signup_data.email,
            password_hash=password_hash,
            full_name=signup_data.full_name,
            email_verification_token=hash_token(verification_token),
            email_verification_sent_at=datetime.utcnow(),
        )

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        # Create audit log
        await self._create_audit_log(
            user_id=user.id,
            action="signup",
            client_info=client_info,
            metadata={"email": user.email},
        )

        # Send verification email
        await email_service.send_verification_email(user.email, verification_token)

        logger.info("user_created", user_id=str(user.id), email=user.email)
        return user

    async def verify_email(self, token: str) -> User:
        """
        Verify user email with token.

        Args:
            token: Verification token

        Returns:
            Verified user

        Raises:
            ValueError: If token is invalid or expired
        """
        token_hash = hash_token(token)

        result = await self.db.execute(
            select(User).where(
                User.email_verification_token == token_hash,
                User.deleted_at.is_(None),
            )
        )
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("Invalid verification token")

        # Check if token is expired (24 hours)
        if user.email_verification_sent_at:
            expires_at = user.email_verification_sent_at + timedelta(hours=24)
            if datetime.utcnow() > expires_at:
                raise ValueError("Verification token has expired")

        # Mark email as verified
        user.email_verified = True
        user.email_verification_token = None
        user.email_verification_sent_at = None

        await self.db.commit()
        await self.db.refresh(user)

        logger.info("email_verified", user_id=str(user.id))
        return user

    async def authenticate_user(
        self,
        email: str,
        password: str,
        client_info: dict,
    ) -> Tuple[Optional[User], bool]:
        """
        Authenticate user with email and password.

        Args:
            email: User email
            password: User password
            client_info: Client IP and user agent

        Returns:
            Tuple of (User, requires_mfa)
            - If password is correct but MFA is enabled, returns (User, True)
            - If authentication is successful and MFA is not enabled, returns (User, False)
            - If authentication fails, returns (None, False)
        """
        # Fetch user
        result = await self.db.execute(
            select(User).where(User.email == email, User.deleted_at.is_(None))
        )
        user = result.scalar_one_or_none()

        if not user:
            # Log failed attempt
            await self._create_audit_log(
                user_id=None,
                action="login_failed",
                client_info=client_info,
                metadata={"email": email, "reason": "user_not_found"},
                success=False,
            )
            return None, False

        # Check if account is locked
        if user.is_locked:
            if user.locked_until and user.locked_until > datetime.utcnow():
                await self._create_audit_log(
                    user_id=user.id,
                    action="login_failed",
                    client_info=client_info,
                    metadata={"reason": "account_locked"},
                    success=False,
                )
                return None, False
            else:
                # Unlock account
                user.is_locked = False
                user.locked_until = None
                user.failed_login_attempts = 0
                await self.db.commit()

        # Verify password
        if not verify_password(password, user.password_hash):
            # Increment failed attempts
            user.failed_login_attempts += 1

            # Lock account if too many failed attempts
            if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
                user.is_locked = True
                user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
                logger.warning("account_locked", user_id=str(user.id))

            await self.db.commit()

            await self._create_audit_log(
                user_id=user.id,
                action="login_failed",
                client_info=client_info,
                metadata={"reason": "invalid_password"},
                success=False,
            )
            return None, False

        # Reset failed attempts on successful password verification
        user.failed_login_attempts = 0
        await self.db.commit()

        # Check if MFA is required
        if user.mfa_enabled:
            return user, True

        # Update last login
        user.last_login_at = datetime.utcnow()
        await self.db.commit()

        await self._create_audit_log(
            user_id=user.id,
            action="login",
            client_info=client_info,
        )

        return user, False

    async def verify_mfa_and_complete_login(
        self,
        user: User,
        mfa_code: str,
        client_info: dict,
    ) -> bool:
        """
        Verify MFA code and complete login.

        Args:
            user: User object
            mfa_code: 6-digit TOTP code or backup code
            client_info: Client information

        Returns:
            True if MFA verification successful

        Raises:
            ValueError: If MFA is not enabled or code is invalid
        """
        if not user.mfa_enabled or not user.mfa_secret:
            raise ValueError("MFA is not enabled")

        # Decrypt MFA secret
        mfa_secret = decrypt_field(user.mfa_secret)

        # Try TOTP code first
        if len(mfa_code) == 6 and mfa_code.isdigit():
            if verify_totp(mfa_secret, mfa_code):
                user.last_login_at = datetime.utcnow()
                await self.db.commit()

                await self._create_audit_log(
                    user_id=user.id,
                    action="login_mfa_success",
                    client_info=client_info,
                )
                return True

        # Try backup code
        result = await self.db.execute(
            select(MFABackupCode).where(
                MFABackupCode.user_id == user.id,
                MFABackupCode.is_used == False,
            )
        )
        backup_codes = result.scalars().all()

        for backup_code in backup_codes:
            if verify_password(mfa_code.upper(), backup_code.code_hash):
                # Mark backup code as used
                backup_code.is_used = True
                backup_code.used_at = datetime.utcnow()

                user.last_login_at = datetime.utcnow()
                await self.db.commit()

                await self._create_audit_log(
                    user_id=user.id,
                    action="login_mfa_backup_code_used",
                    client_info=client_info,
                )
                return True

        # Invalid code
        await self._create_audit_log(
            user_id=user.id,
            action="login_mfa_failed",
            client_info=client_info,
            success=False,
        )
        raise ValueError("Invalid MFA code")

    async def create_session(
        self,
        user: User,
        client_info: dict,
    ) -> Tuple[str, str]:
        """
        Create a new session with access and refresh tokens.

        Args:
            user: User object
            client_info: Client information

        Returns:
            Tuple of (access_token, refresh_token)
        """
        # Generate tokens
        access_token = create_access_token({"sub": str(user.id)})
        refresh_token = create_refresh_token({"sub": str(user.id)})

        # Store refresh token (hashed) in database
        session = Session(
            user_id=user.id,
            refresh_token_hash=hash_token(refresh_token),
            device_info=client_info,
            expires_at=datetime.utcnow() + timedelta(days=7),
        )
        self.db.add(session)
        await self.db.commit()

        logger.info("session_created", user_id=str(user.id), session_id=str(session.id))
        return access_token, refresh_token

    async def refresh_session(
        self,
        refresh_token: str,
        client_info: dict,
    ) -> Tuple[str, str]:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: Refresh token
            client_info: Client information

        Returns:
            Tuple of (new_access_token, new_refresh_token)

        Raises:
            ValueError: If refresh token is invalid or expired
        """
        token_hash = hash_token(refresh_token)

        # Fetch session
        result = await self.db.execute(
            select(Session).where(
                Session.refresh_token_hash == token_hash,
                Session.is_revoked == False,
            )
        )
        session = result.scalar_one_or_none()

        if not session:
            raise ValueError("Invalid refresh token")

        # Check if token is expired
        if datetime.utcnow() > session.expires_at:
            raise ValueError("Refresh token has expired")

        # Check for token reuse (security measure)
        if session.is_used:
            # Token reuse detected - revoke all user sessions
            logger.warning("token_reuse_detected", user_id=str(session.user_id))
            await self._revoke_all_user_sessions(session.user_id)
            raise ValueError("Token reuse detected. All sessions have been revoked.")

        # Mark current token as used
        session.is_used = True
        session.used_at = datetime.utcnow()

        # Create new session with token rotation
        user = await self.db.get(User, session.user_id)
        new_access_token, new_refresh_token = await self.create_session(user, client_info)

        await self.db.commit()

        logger.info("session_refreshed", user_id=str(session.user_id))
        return new_access_token, new_refresh_token

    async def logout(self, refresh_token: str) -> None:
        """
        Logout user by revoking session.

        Args:
            refresh_token: Refresh token to revoke
        """
        token_hash = hash_token(refresh_token)

        result = await self.db.execute(
            select(Session).where(Session.refresh_token_hash == token_hash)
        )
        session = result.scalar_one_or_none()

        if session:
            session.is_revoked = True
            session.revoked_at = datetime.utcnow()
            await self.db.commit()

            await self._create_audit_log(
                user_id=session.user_id,
                action="logout",
                client_info={},
            )
            logger.info("session_revoked", session_id=str(session.id))

    async def enable_mfa(self, user: User) -> Tuple[str, str, list]:
        """
        Enable MFA for user.

        Args:
            user: User object

        Returns:
            Tuple of (secret, qr_uri, backup_codes)
        """
        # Generate TOTP secret
        secret = generate_totp_secret()
        qr_uri = generate_totp_uri(secret, user.email)

        # Generate backup codes
        backup_codes = generate_backup_codes(10)

        # Store encrypted secret (will be committed after verification)
        user.mfa_secret = encrypt_field(secret)

        # Store hashed backup codes
        for code in backup_codes:
            backup_code = MFABackupCode(
                user_id=user.id,
                code_hash=hash_password(code),
            )
            self.db.add(backup_code)

        # Don't enable MFA yet - wait for verification
        await self.db.commit()

        logger.info("mfa_setup_initiated", user_id=str(user.id))
        return secret, qr_uri, backup_codes

    async def confirm_mfa(self, user: User, code: str, client_info: dict) -> None:
        """
        Confirm and activate MFA.

        Args:
            user: User object
            code: 6-digit TOTP code
            client_info: Client information

        Raises:
            ValueError: If code is invalid
        """
        if not user.mfa_secret:
            raise ValueError("MFA setup not initiated")

        # Decrypt and verify code
        mfa_secret = decrypt_field(user.mfa_secret)
        if not verify_totp(mfa_secret, code):
            raise ValueError("Invalid MFA code")

        # Enable MFA
        user.mfa_enabled = True
        await self.db.commit()

        await self._create_audit_log(
            user_id=user.id,
            action="mfa_enabled",
            client_info=client_info,
        )

        # Send confirmation email
        await email_service.send_mfa_enabled_email(user.email)

        logger.info("mfa_enabled", user_id=str(user.id))

    async def disable_mfa(self, user: User, client_info: dict) -> None:
        """
        Disable MFA for user.

        Args:
            user: User object
            client_info: Client information
        """
        user.mfa_enabled = False
        user.mfa_secret = None

        # Delete backup codes
        await self.db.execute(
            MFABackupCode.__table__.delete().where(MFABackupCode.user_id == user.id)
        )

        await self.db.commit()

        await self._create_audit_log(
            user_id=user.id,
            action="mfa_disabled",
            client_info=client_info,
        )

        logger.info("mfa_disabled", user_id=str(user.id))

    async def initiate_password_reset(self, email: str) -> None:
        """
        Initiate password reset flow.

        Args:
            email: User email
        """
        result = await self.db.execute(
            select(User).where(User.email == email, User.deleted_at.is_(None))
        )
        user = result.scalar_one_or_none()

        # Always return success to prevent email enumeration
        if not user:
            logger.info("password_reset_nonexistent_email", email=email)
            return

        # Generate reset token
        reset_token = generate_secure_token()
        user.password_reset_token = hash_token(reset_token)
        user.password_reset_sent_at = datetime.utcnow()

        await self.db.commit()

        # Send reset email
        await email_service.send_password_reset_email(user.email, reset_token)

        logger.info("password_reset_initiated", user_id=str(user.id))

    async def reset_password(self, token: str, new_password: str) -> None:
        """
        Reset password with token.

        Args:
            token: Password reset token
            new_password: New password

        Raises:
            ValueError: If token is invalid or expired
        """
        token_hash = hash_token(token)

        result = await self.db.execute(
            select(User).where(
                User.password_reset_token == token_hash,
                User.deleted_at.is_(None),
            )
        )
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("Invalid reset token")

        # Check if token is expired (1 hour)
        if user.password_reset_sent_at:
            expires_at = user.password_reset_sent_at + timedelta(hours=1)
            if datetime.utcnow() > expires_at:
                raise ValueError("Reset token has expired")

        # Update password
        user.password_hash = hash_password(new_password)
        user.password_reset_token = None
        user.password_reset_sent_at = None

        # Revoke all sessions for security
        await self._revoke_all_user_sessions(user.id)

        await self.db.commit()

        logger.info("password_reset_completed", user_id=str(user.id))

    async def _revoke_all_user_sessions(self, user_id: UUID) -> None:
        """Revoke all sessions for a user."""
        result = await self.db.execute(
            select(Session).where(
                Session.user_id == user_id,
                Session.is_revoked == False,
            )
        )
        sessions = result.scalars().all()

        for session in sessions:
            session.is_revoked = True
            session.revoked_at = datetime.utcnow()

        await self.db.commit()
        logger.info("all_sessions_revoked", user_id=str(user_id))

    async def _create_audit_log(
        self,
        action: str,
        client_info: dict,
        user_id: Optional[UUID] = None,
        metadata: Optional[dict] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> None:
        """Create an audit log entry."""
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            ip_address=client_info.get("ip_address"),
            user_agent=client_info.get("user_agent"),
            metadata=metadata or {},
            success=success,
            error_message=error_message,
        )
        self.db.add(audit_log)
        # Don't commit here - let the caller handle the transaction
