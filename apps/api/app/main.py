"""
Main FastAPI application entry point.
Includes security headers, CORS, rate limiting, and comprehensive error handling.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import engine, init_db
from app.core.logging import configure_logging
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware

# Configure structured logging
configure_logging()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan handler for startup and shutdown events."""
    # Startup
    logger.info("application_starting", environment=settings.ENVIRONMENT)
    await init_db()
    logger.info("database_initialized")

    yield

    # Shutdown
    logger.info("application_shutting_down")
    await engine.dispose()
    logger.info("database_connections_closed")


# Create FastAPI application
app = FastAPI(
    title="Smart Stock Bot API",
    description="Production-ready stock trading and portfolio management API",
    version="1.0.0",
    docs_url=f"{settings.API_PREFIX}/docs" if settings.DEBUG else None,
    redoc_url=f"{settings.API_PREFIX}/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Security middleware
app.add_middleware(SecurityHeadersMiddleware)

# Request ID middleware (for tracing)
app.add_middleware(RequestIDMiddleware)

# Rate limiting
if settings.RATE_LIMIT_ENABLED:
    app.add_middleware(RateLimitMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# Trusted host (prevents host header injection)
if not settings.DEBUG:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS,
    )


# Health check endpoint
@app.get("/healthz", tags=["Health"])
async def health_check():
    """Health check endpoint for load balancers and monitoring."""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "version": "1.0.0",
    }


# Readiness check endpoint
@app.get("/readyz", tags=["Health"])
async def readiness_check():
    """Readiness check endpoint - verifies database connectivity."""
    from app.core.database import SessionLocal

    try:
        async with SessionLocal() as session:
            await session.execute("SELECT 1")
        return {"status": "ready"}
    except Exception as e:
        logger.error("readiness_check_failed", error=str(e))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "error": "database_unavailable"},
        )


# Metrics endpoint (basic)
@app.get("/metrics", tags=["Monitoring"])
async def metrics():
    """Basic metrics endpoint."""
    # TODO: Implement Prometheus metrics
    return {"message": "Metrics endpoint - TODO: implement Prometheus metrics"}


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    request_id = request.state.request_id if hasattr(request.state, "request_id") else "unknown"

    logger.error(
        "unhandled_exception",
        request_id=request_id,
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred" if not settings.DEBUG else str(exc),
            "request_id": request_id,
        },
    )


# Import and include routers
from app.api.v1 import auth

app.include_router(auth.router, prefix=f"{settings.API_PREFIX}/auth", tags=["Auth"])


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Smart Stock Bot API",
        "version": "1.0.0",
        "status": "operational",
        "docs": f"{settings.API_PREFIX}/docs" if settings.DEBUG else "disabled",
    }
