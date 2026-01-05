"""
Application configuration using Pydantic settings.
Loads from environment variables with validation.
"""
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=False)
    SECRET_KEY: str = Field(min_length=32)
    API_PREFIX: str = Field(default="/api/v1")
    ALLOWED_ORIGINS: List[str] = Field(default=["http://localhost:3000"])
    ALLOWED_HOSTS: List[str] = Field(default=["localhost", "127.0.0.1"])

    # Database
    DATABASE_URL: str = Field(...)

    # Redis
    REDIS_URL: str = Field(...)

    # JWT
    JWT_SECRET_KEY: str = Field(min_length=32)
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)

    # Encryption (for sensitive data at rest)
    ENCRYPTION_KEY: str = Field(min_length=32)

    # Email
    SMTP_HOST: str = Field(default="smtp.gmail.com")
    SMTP_PORT: int = Field(default=587)
    SMTP_USER: str = Field(default="")
    SMTP_PASSWORD: str = Field(default="")
    SMTP_FROM: str = Field(default="noreply@smartstockbot.com")

    # Trading
    TRADING_MODE: str = Field(default="paper")
    ENABLE_LIVE_TRADING: bool = Field(default=False)

    # Alpaca
    ALPACA_API_KEY: str = Field(default="")
    ALPACA_API_SECRET: str = Field(default="")
    ALPACA_BASE_URL: str = Field(default="https://paper-api.alpaca.markets")
    ALPACA_MARKET_DATA_URL: str = Field(default="https://data.alpaca.markets")

    # Plaid
    PLAID_CLIENT_ID: str = Field(default="")
    PLAID_SECRET: str = Field(default="")
    PLAID_ENV: str = Field(default="sandbox")

    # Stripe
    STRIPE_API_KEY: str = Field(default="")
    STRIPE_WEBHOOK_SECRET: str = Field(default="")

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = Field(default=True)
    RATE_LIMIT_PER_MINUTE: int = Field(default=60)

    # Security
    SESSION_COOKIE_SECURE: bool = Field(default=False)
    SESSION_COOKIE_SAMESITE: str = Field(default="strict")
    CSRF_ENABLED: bool = Field(default=True)

    # Feature Flags
    ENABLE_MFA: bool = Field(default=True)
    ENABLE_EMAIL_VERIFICATION: bool = Field(default=True)
    ENABLE_BOT_AUTO_TRADE: bool = Field(default=False)

    # Monitoring
    LOG_LEVEL: str = Field(default="INFO")
    SENTRY_DSN: str = Field(default="")

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse comma-separated CORS origins."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, v):
        """Parse comma-separated allowed hosts."""
        if isinstance(v, str):
            return [host.strip() for host in v.split(",")]
        return v


# Global settings instance
settings = Settings()
