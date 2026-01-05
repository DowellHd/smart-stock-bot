"""
Authentication schemas for request/response validation.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.security import validate_password_strength


# ============================================================================
# Request Schemas
# ============================================================================


class SignupRequest(BaseModel):
    """User signup request."""
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = Field(None, max_length=255)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        is_valid, error_message = validate_password_strength(v)
        if not is_valid:
            raise ValueError(error_message)
        return v


class LoginRequest(BaseModel):
    """User login request."""
    email: EmailStr
    password: str
    mfa_code: Optional[str] = Field(None, pattern=r"^\d{6}$")


class RefreshTokenRequest(BaseModel):
    """Refresh token request (body is empty, token comes from cookie)."""
    pass


class PasswordResetRequest(BaseModel):
    """Password reset request."""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation."""
    token: str
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        is_valid, error_message = validate_password_strength(v)
        if not is_valid:
            raise ValueError(error_message)
        return v


class ChangePasswordRequest(BaseModel):
    """Change password request."""
    current_password: str
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        is_valid, error_message = validate_password_strength(v)
        if not is_valid:
            raise ValueError(error_message)
        return v


class EmailVerificationRequest(BaseModel):
    """Email verification request."""
    token: str


class ResendVerificationRequest(BaseModel):
    """Resend verification email request."""
    email: EmailStr


# ============================================================================
# MFA Schemas
# ============================================================================


class MFAEnableRequest(BaseModel):
    """MFA enable request."""
    password: str


class MFAConfirmRequest(BaseModel):
    """MFA confirmation request."""
    code: str = Field(..., pattern=r"^\d{6}$")


class MFADisableRequest(BaseModel):
    """MFA disable request."""
    password: str
    code: str = Field(..., pattern=r"^\d{6}$")


class MFAVerifyBackupCodeRequest(BaseModel):
    """MFA backup code verification request."""
    code: str = Field(..., min_length=8, max_length=8)


# ============================================================================
# Response Schemas
# ============================================================================


class TokenResponse(BaseModel):
    """Token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserResponse(BaseModel):
    """User response."""
    id: UUID
    email: str
    full_name: Optional[str]
    email_verified: bool
    mfa_enabled: bool
    role: str
    paper_trading_approved: bool
    live_trading_approved: bool
    preferences: dict
    created_at: datetime
    last_login_at: Optional[datetime]

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    """Login response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
    requires_mfa: bool = False


class SignupResponse(BaseModel):
    """Signup response."""
    user: UserResponse
    message: str = "Account created successfully. Please verify your email."


class MFAEnableResponse(BaseModel):
    """MFA enable response."""
    secret: str
    qr_code_uri: str
    backup_codes: list[str]
    message: str = "MFA setup initiated. Scan QR code and verify with a code to complete setup."


class MFAStatusResponse(BaseModel):
    """MFA status response."""
    mfa_enabled: bool
    backup_codes_remaining: int


class SessionResponse(BaseModel):
    """Session response."""
    id: UUID
    device_info: dict
    last_used_at: datetime
    created_at: datetime
    is_current: bool = False

    class Config:
        from_attributes = True


class SessionListResponse(BaseModel):
    """List of user sessions."""
    sessions: list[SessionResponse]


# ============================================================================
# Generic Response Schemas
# ============================================================================


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
    success: bool = True


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    message: str
    details: Optional[dict] = None
