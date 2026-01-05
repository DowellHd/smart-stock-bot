"""
Authentication API endpoints.
"""
from datetime import timedelta
from typing import Optional

import structlog
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_client_info, get_current_user
from app.core.security import verify_password
from app.models.user import Session as SessionModel
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    EmailVerificationRequest,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    MFAConfirmRequest,
    MFADisableRequest,
    MFAEnableRequest,
    MFAEnableResponse,
    MFAStatusResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    ResendVerificationRequest,
    SessionListResponse,
    SessionResponse,
    SignupRequest,
    SignupResponse,
    TokenResponse,
    UserResponse,
)
from app.services.auth import AuthService

logger = structlog.get_logger()

router = APIRouter()


# ============================================================================
# Authentication Endpoints
# ============================================================================


@router.post("/register", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    signup_data: SignupRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user account.

    - Creates user with hashed password
    - Sends email verification
    - Returns user object
    """
    client_info = get_client_info(request)
    auth_service = AuthService(db)

    try:
        user = await auth_service.create_user(signup_data, client_info)
        return SignupResponse(user=UserResponse.model_validate(user))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    response: Response,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Login with email and password.

    - Validates credentials
    - If MFA is enabled, returns requires_mfa=True (no tokens yet)
    - If MFA is not enabled, creates session and returns tokens
    - Refresh token is set as httpOnly cookie
    """
    client_info = get_client_info(request)
    auth_service = AuthService(db)

    # Authenticate user
    user, requires_mfa = await auth_service.authenticate_user(
        login_data.email,
        login_data.password,
        client_info,
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # If MFA is required
    if requires_mfa:
        # If MFA code is provided, verify it
        if login_data.mfa_code:
            try:
                await auth_service.verify_mfa_and_complete_login(
                    user, login_data.mfa_code, client_info
                )
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=str(e),
                )
        else:
            # MFA code required but not provided
            return LoginResponse(
                access_token="",
                expires_in=0,
                user=UserResponse.model_validate(user),
                requires_mfa=True,
            )

    # Create session and tokens
    access_token, refresh_token = await auth_service.create_session(user, client_info)

    # Set refresh token in httpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        max_age=60 * 60 * 24 * 7,  # 7 days
    )

    return LoginResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
        requires_mfa=False,
    )


@router.post("/mfa/verify", response_model=LoginResponse)
async def verify_mfa(
    request: Request,
    response: Response,
    email: str,
    mfa_code: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Verify MFA code and complete login.

    Used when MFA is required after initial login.
    """
    client_info = get_client_info(request)
    auth_service = AuthService(db)

    # Fetch user
    result = await db.execute(
        select(User).where(User.email == email, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Verify MFA
    try:
        await auth_service.verify_mfa_and_complete_login(user, mfa_code, client_info)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    # Create session
    access_token, refresh_token = await auth_service.create_session(user, client_info)

    # Set refresh token in cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        max_age=60 * 60 * 24 * 7,
    )

    return LoginResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
    refresh_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh access token using refresh token from cookie.

    - Validates refresh token
    - Implements token rotation (old token is invalidated)
    - Returns new access token
    - Sets new refresh token in cookie
    """
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )

    client_info = get_client_info(request)
    auth_service = AuthService(db)

    try:
        new_access_token, new_refresh_token = await auth_service.refresh_session(
            refresh_token, client_info
        )
    except ValueError as e:
        # Clear invalid cookie
        response.delete_cookie("refresh_token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    # Set new refresh token in cookie
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        max_age=60 * 60 * 24 * 7,
    )

    return TokenResponse(
        access_token=new_access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    refresh_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Logout and revoke current session.

    - Revokes refresh token
    - Clears cookie
    """
    if refresh_token:
        auth_service = AuthService(db)
        await auth_service.logout(refresh_token)

    # Clear cookie
    response.delete_cookie("refresh_token")

    return MessageResponse(message="Logged out successfully")


# ============================================================================
# Email Verification
# ============================================================================


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    verification_data: EmailVerificationRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Verify email address with token.

    Token is sent to user's email after registration.
    """
    auth_service = AuthService(db)

    try:
        await auth_service.verify_email(verification_data.token)
        return MessageResponse(message="Email verified successfully")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(
    resend_data: ResendVerificationRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Resend email verification.

    Used when user didn't receive the initial verification email.
    """
    # This would need to be implemented in auth_service
    # For now, return a placeholder
    return MessageResponse(message="Verification email sent")


# ============================================================================
# Password Reset
# ============================================================================


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    reset_data: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Initiate password reset flow.

    Sends password reset email with token.
    Always returns success to prevent email enumeration.
    """
    auth_service = AuthService(db)
    await auth_service.initiate_password_reset(reset_data.email)

    return MessageResponse(
        message="If the email exists, a password reset link has been sent"
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    reset_data: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
):
    """
    Reset password with token.

    - Validates token
    - Updates password
    - Revokes all sessions
    """
    auth_service = AuthService(db)

    try:
        await auth_service.reset_password(reset_data.token, reset_data.new_password)
        return MessageResponse(message="Password reset successfully")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    change_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Change password (requires authentication).

    - Verifies current password
    - Updates to new password
    """
    # Verify current password
    if not verify_password(change_data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    # Update password
    from app.core.security import hash_password

    current_user.password_hash = hash_password(change_data.new_password)
    await db.commit()

    return MessageResponse(message="Password changed successfully")


# ============================================================================
# User Info
# ============================================================================


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current authenticated user information."""
    return UserResponse.model_validate(current_user)


# ============================================================================
# MFA Management
# ============================================================================


@router.post("/mfa/enable", response_model=MFAEnableResponse)
async def enable_mfa(
    mfa_data: MFAEnableRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Enable MFA for current user.

    - Verifies password
    - Generates TOTP secret and QR code
    - Returns backup codes
    - User must verify with a code to complete setup
    """
    # Verify password
    if not verify_password(mfa_data.password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid password",
        )

    if current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is already enabled",
        )

    auth_service = AuthService(db)
    secret, qr_uri, backup_codes = await auth_service.enable_mfa(current_user)

    return MFAEnableResponse(
        secret=secret,
        qr_code_uri=qr_uri,
        backup_codes=backup_codes,
    )


@router.post("/mfa/confirm", response_model=MessageResponse)
async def confirm_mfa(
    request: Request,
    confirm_data: MFAConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Confirm and activate MFA.

    Verifies the TOTP code and enables MFA.
    """
    client_info = get_client_info(request)
    auth_service = AuthService(db)

    try:
        await auth_service.confirm_mfa(current_user, confirm_data.code, client_info)
        return MessageResponse(message="MFA enabled successfully")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/mfa/disable", response_model=MessageResponse)
async def disable_mfa(
    request: Request,
    disable_data: MFADisableRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Disable MFA.

    Requires password and MFA code verification.
    """
    # Verify password
    if not verify_password(disable_data.password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid password",
        )

    if not current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is not enabled",
        )

    # Verify MFA code
    from app.core.security import decrypt_field, verify_totp

    mfa_secret = decrypt_field(current_user.mfa_secret)
    if not verify_totp(mfa_secret, disable_data.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MFA code",
        )

    client_info = get_client_info(request)
    auth_service = AuthService(db)
    await auth_service.disable_mfa(current_user, client_info)

    return MessageResponse(message="MFA disabled successfully")


@router.get("/mfa/status", response_model=MFAStatusResponse)
async def get_mfa_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get MFA status and remaining backup codes."""
    from app.models.user import MFABackupCode

    # Count unused backup codes
    result = await db.execute(
        select(MFABackupCode).where(
            MFABackupCode.user_id == current_user.id,
            MFABackupCode.is_used == False,
        )
    )
    backup_codes_count = len(result.scalars().all())

    return MFAStatusResponse(
        mfa_enabled=current_user.mfa_enabled,
        backup_codes_remaining=backup_codes_count,
    )


# ============================================================================
# Session Management
# ============================================================================


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    current_user: User = Depends(get_current_user),
    refresh_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """
    List all active sessions for current user.

    Shows device info and last activity for each session.
    """
    from app.core.security import hash_token

    # Get current session token hash
    current_token_hash = hash_token(refresh_token) if refresh_token else None

    # Fetch user sessions
    result = await db.execute(
        select(SessionModel).where(
            SessionModel.user_id == current_user.id,
            SessionModel.is_revoked == False,
        ).order_by(SessionModel.last_used_at.desc())
    )
    sessions = result.scalars().all()

    session_responses = []
    for session in sessions:
        is_current = session.refresh_token_hash == current_token_hash
        session_responses.append(
            SessionResponse(
                id=session.id,
                device_info=session.device_info,
                last_used_at=session.last_used_at,
                created_at=session.created_at,
                is_current=is_current,
            )
        )

    return SessionListResponse(sessions=session_responses)


@router.post("/sessions/{session_id}/revoke", response_model=MessageResponse)
async def revoke_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke a specific session.

    User can revoke their own sessions (e.g., logout from other devices).
    """
    from uuid import UUID

    # Fetch session
    session = await db.get(SessionModel, UUID(session_id))

    if not session or session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    if session.is_revoked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session already revoked",
        )

    # Revoke session
    from datetime import datetime

    session.is_revoked = True
    session.revoked_at = datetime.utcnow()
    await db.commit()

    return MessageResponse(message="Session revoked successfully")
