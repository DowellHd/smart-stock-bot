"""
Trading signal API endpoints for generating buy/sell signals.
"""
import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import get_current_user
from app.core.entitlements import get_entitlements, Entitlements
from app.models.user import User
from app.schemas.signals import (
    GenerateSignalRequest,
    SignalResponse,
    BulkSignalRequest,
    BulkSignalResponse,
)
from app.services.signals import signal_service

logger = structlog.get_logger()

router = APIRouter()


@router.post("/generate", response_model=SignalResponse)
async def generate_signal(
    request: GenerateSignalRequest,
    current_user: User = Depends(get_current_user),
    entitlements: Entitlements = Depends(get_entitlements),
):
    """
    Generate trading signal for a symbol.

    Uses technical analysis strategies to generate buy/sell/hold signals.

    **Tiered Access:**
    - **Free Plan**: 15-minute delayed signals
    - **Starter Plan**: Real-time signals
    - **Pro Plan**: Real-time signals

    **Supported Strategies:**
    - `sma_crossover`: Simple Moving Average crossover (50/200-day)

    **Returns:**
    Trading signal with action, confidence, and timing information.
    """
    try:
        signal = await signal_service.generate_signal(
            symbol=request.symbol.upper(),
            strategy=request.strategy,
            user_plan=entitlements.plan_name,
        )

        logger.info(
            "signal_generated_via_api",
            user_id=str(current_user.id),
            symbol=request.symbol,
            action=signal["action"],
            plan=entitlements.plan_name,
        )

        return SignalResponse(**signal)

    except Exception as e:
        logger.error(
            "generate_signal_failed",
            user_id=str(current_user.id),
            symbol=request.symbol,
            strategy=request.strategy,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate signal for {request.symbol}",
        )


@router.post("/bulk", response_model=BulkSignalResponse)
async def generate_bulk_signals(
    request: BulkSignalRequest,
    current_user: User = Depends(get_current_user),
    entitlements: Entitlements = Depends(get_entitlements),
):
    """
    Generate signals for multiple symbols.

    **Tiered Access:**
    - **Free Plan**: 15-minute delayed signals, max 5 symbols
    - **Starter Plan**: Real-time signals, max 20 symbols
    - **Pro Plan**: Real-time signals, max 20 symbols

    **Returns:**
    List of trading signals for all requested symbols.
    """
    try:
        # Enforce max symbols based on plan
        max_symbols = entitlements.get_feature_value("max_watchlist_symbols", 5)
        if len(request.symbols) > max_symbols:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Your plan allows max {max_symbols} symbols. Upgrade to analyze more.",
            )

        signals = await signal_service.generate_bulk_signals(
            symbols=[s.upper() for s in request.symbols],
            strategy=request.strategy,
            user_plan=entitlements.plan_name,
        )

        logger.info(
            "bulk_signals_generated",
            user_id=str(current_user.id),
            count=len(signals),
            plan=entitlements.plan_name,
        )

        return BulkSignalResponse(
            signals=[SignalResponse(**s) for s in signals],
            total=len(signals),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "generate_bulk_signals_failed",
            user_id=str(current_user.id),
            symbols=request.symbols,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate bulk signals",
        )


@router.get("/delay-info")
async def get_signal_delay_info(
    entitlements: Entitlements = Depends(get_entitlements),
):
    """
    Get information about signal delays for current user's plan.

    **Returns:**
    Delay information and plan details.
    """
    delay_minutes = signal_service._get_signal_delay(entitlements.plan_name)

    return {
        "plan": entitlements.plan_name,
        "delay_minutes": delay_minutes,
        "is_realtime": delay_minutes == 0,
        "message": (
            "You have real-time signal access"
            if delay_minutes == 0
            else f"Signals are delayed by {delay_minutes} minutes on your current plan"
        ),
    }
