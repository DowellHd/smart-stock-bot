"""
Security utilities for password hashing, encryption, and JWT tokens.
"""
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

import pyotp
from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# Password hashing context (Argon2id - OWASP recommended)
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# Encryption cipher for sensitive data at rest
# In production, load key from secure key management service
cipher = Fernet(settings.ENCRYPTION_KEY.encode())


# ============================================================================
# Password Hashing
# ============================================================================


def hash_password(password: str) -> str:
    """Hash a password using Argon2id."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ============================================================================
# Token Hashing (for refresh tokens, verification tokens, etc.)
# ============================================================================


def hash_token(token: str) -> str:
    """Hash a token using SHA-256."""
    return hashlib.sha256(token.encode()).hexdigest()


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_urlsafe(length)


# ============================================================================
# Field Encryption (for sensitive data at rest)
# ============================================================================


def encrypt_field(value: str) -> str:
    """Encrypt a field value for storage."""
    return cipher.encrypt(value.encode()).decode()


def decrypt_field(encrypted_value: str) -> str:
    """Decrypt an encrypted field value."""
    return cipher.decrypt(encrypted_value.encode()).decode()


# ============================================================================
# JWT Tokens
# ============================================================================


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        data: Dictionary of claims to encode in the token
        expires_delta: Token expiration time (defaults to ACCESS_TOKEN_EXPIRE_MINUTES)

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access",
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """
    Create a JWT refresh token.

    Args:
        data: Dictionary of claims to encode in the token

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh",
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token string

    Returns:
        Dictionary of decoded claims

    Raises:
        JWTError: If token is invalid or expired
    """
    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
    return payload


# ============================================================================
# MFA (TOTP)
# ============================================================================


def generate_totp_secret() -> str:
    """Generate a new TOTP secret."""
    return pyotp.random_base32()


def generate_totp_uri(secret: str, email: str, issuer: str = "Smart Stock Bot") -> str:
    """
    Generate a TOTP provisioning URI for QR code generation.

    Args:
        secret: TOTP secret
        email: User's email
        issuer: Application name

    Returns:
        TOTP provisioning URI
    """
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=issuer)


def verify_totp(secret: str, code: str) -> bool:
    """
    Verify a TOTP code.

    Args:
        secret: TOTP secret
        code: 6-digit TOTP code

    Returns:
        True if code is valid, False otherwise
    """
    totp = pyotp.TOTP(secret)
    # Allow 1 period (30 seconds) of clock drift
    return totp.verify(code, valid_window=1)


# ============================================================================
# Backup Codes
# ============================================================================


def generate_backup_codes(count: int = 10) -> list[str]:
    """
    Generate MFA backup codes.

    Args:
        count: Number of backup codes to generate

    Returns:
        List of backup codes (8-character alphanumeric)
    """
    codes = []
    for _ in range(count):
        # Generate 8-character alphanumeric code
        code = secrets.token_hex(4).upper()  # 8 hex characters
        codes.append(code)
    return codes


# ============================================================================
# Password Validation
# ============================================================================


def validate_password_strength(password: str) -> tuple[bool, Optional[str]]:
    """
    Validate password strength.

    Requirements:
    - At least 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character

    Args:
        password: Password to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"

    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"

    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"

    special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    if not any(c in special_chars for c in password):
        return False, "Password must contain at least one special character"

    return True, None
