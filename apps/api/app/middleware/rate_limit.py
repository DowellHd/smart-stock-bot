"""
Rate limiting middleware using Redis.
"""
import time
from typing import Optional

import redis.asyncio as redis
import structlog
from fastapi import status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.config import settings

logger = structlog.get_logger()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using sliding window algorithm.
    Limits requests per IP address.
    """

    def __init__(self, app):
        super().__init__(app)
        self.redis_client: Optional[redis.Redis] = None
        self.window_size = 60  # 60 seconds
        self.max_requests = settings.RATE_LIMIT_PER_MINUTE

    async def get_redis(self):
        """Get or create Redis client."""
        if self.redis_client is None:
            self.redis_client = await redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
        return self.redis_client

    async def is_rate_limited(self, key: str) -> bool:
        """Check if the key is rate limited using sliding window."""
        try:
            redis_client = await self.get_redis()
            current_time = time.time()
            window_start = current_time - self.window_size

            # Remove old entries
            await redis_client.zremrangebyscore(key, 0, window_start)

            # Count requests in current window
            request_count = await redis_client.zcard(key)

            if request_count >= self.max_requests:
                return True

            # Add current request
            await redis_client.zadd(key, {str(current_time): current_time})

            # Set expiry
            await redis_client.expire(key, self.window_size)

            return False

        except Exception as e:
            logger.error("rate_limit_check_failed", error=str(e))
            # Fail open - allow request if rate limiting fails
            return False

    def get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for X-Forwarded-For header (if behind proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        # Check for X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to client host
        if request.client:
            return request.client.host

        return "unknown"

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path in ["/healthz", "/readyz"]:
            return await call_next(request)

        # Get client identifier
        client_ip = self.get_client_ip(request)
        rate_limit_key = f"rate_limit:{client_ip}"

        # Check rate limit
        if await self.is_rate_limited(rate_limit_key):
            logger.warning("rate_limit_exceeded", client_ip=client_ip, path=request.url.path)
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "rate_limit_exceeded",
                    "message": "Too many requests. Please try again later.",
                },
            )

        # Process request
        response = await call_next(request)
        return response
