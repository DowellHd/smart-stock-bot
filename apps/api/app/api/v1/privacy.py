"""
Privacy and data management API endpoints.
"""
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_client_info, get_current_user, require_admin
from app.models.user import User
from app.schemas.privacy import (
    DataExportResponse,
    MessageResponse,
    PreferencesResponse,
    PreferencesUpdateRequest,
)
from app.services.privacy import PrivacyService

logger = structlog.get_logger()

router = APIRouter()


# ============================================================================
# Privacy & Data Management Endpoints
# ============================================================================


@router.get("/export", response_model=DataExportResponse)
async def export_user_data(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Export all user data for GDPR compliance (Right to Access).

    Returns a comprehensive JSON export including:
    - User profile information
    - Active sessions with device information
    - Security settings (MFA status, backup codes count)
    - Trading permissions
    - Privacy preferences and consent settings
    - Audit logs (last 1000 entries)

    **Note:** Sensitive data (passwords, MFA secrets, actual backup codes) are NOT included.

    **Rate Limited:** This endpoint is rate-limited to prevent abuse.
    """
    privacy_service = PrivacyService(db)

    try:
        export_data = await privacy_service.export_user_data(current_user.id)

        # Update audit log with client info (the service creates the log entry)
        # We could enhance this by passing client_info to the service, but for now
        # the service creates a basic log entry
        client_info = get_client_info(request)
        logger.info(
            "data_export_requested",
            user_id=str(current_user.id),
            ip_address=client_info.get("ip_address"),
            user_agent=client_info.get("user_agent"),
        )

        return export_data

    except ValueError as e:
        logger.error(
            "data_export_failed",
            user_id=str(current_user.id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            "data_export_error",
            user_id=str(current_user.id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export user data",
        )


@router.delete("/account", response_model=MessageResponse)
async def delete_user_account(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete user account for GDPR compliance (Right to Erasure).

    Performs a **soft delete** which:
    - Marks the account as deleted (cannot be recovered)
    - Revokes all active sessions (logs user out everywhere)
    - Anonymizes personally identifiable information (PII)
    - Preserves audit trail for compliance purposes

    **Important:**
    - This action is **irreversible**
    - You will be immediately logged out
    - Your data will be anonymized but preserved for audit/legal compliance
    - For complete data removal, contact support (admin required)

    **Rate Limited:** This endpoint is rate-limited to prevent abuse.
    """
    privacy_service = PrivacyService(db)
    client_info = get_client_info(request)

    try:
        await privacy_service.soft_delete_account(current_user.id, client_info)

        logger.info(
            "account_deletion_requested",
            user_id=str(current_user.id),
            email=current_user.email,
            ip_address=client_info.get("ip_address"),
        )

        return MessageResponse(
            message="Account successfully deleted. All sessions have been revoked."
        )

    except ValueError as e:
        logger.error(
            "account_deletion_failed",
            user_id=str(current_user.id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            "account_deletion_error",
            user_id=str(current_user.id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete account",
        )


@router.get("/preferences", response_model=PreferencesResponse)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get user privacy preferences and consent settings.

    Returns current privacy settings including:
    - Analytics consent
    - Email notification preferences
    - Trade confirmation settings
    - Marketing email preferences
    - UI theme preference

    Defaults are returned for any unset preferences.
    """
    privacy_service = PrivacyService(db)

    try:
        preferences = await privacy_service.get_user_preferences(current_user.id)
        return PreferencesResponse(**preferences)

    except ValueError as e:
        logger.error(
            "get_preferences_failed",
            user_id=str(current_user.id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            "get_preferences_error",
            user_id=str(current_user.id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve preferences",
        )


@router.put("/preferences", response_model=PreferencesResponse)
async def update_preferences(
    request: Request,
    preferences_update: PreferencesUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update user privacy preferences and consent settings.

    **Partial Updates Supported:** You can update one or more preferences at a time.
    Only the fields provided will be updated.

    **Available Preferences:**
    - `analytics_consent`: Consent for analytics and tracking (default: false)
    - `email_notifications`: Enable email notifications (default: true)
    - `trade_confirmations`: Email confirmations for trades (default: true)
    - `marketing_emails`: Receive marketing emails (default: false)
    - `theme`: UI theme preference ("light" or "dark", default: "light")

    **Audit Trail:** All preference changes are logged for compliance.
    """
    privacy_service = PrivacyService(db)
    client_info = get_client_info(request)

    # Convert Pydantic model to dict, excluding unset fields
    updates = preferences_update.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No preferences provided for update",
        )

    try:
        updated_preferences = await privacy_service.update_user_preferences(
            current_user.id, updates, client_info
        )

        logger.info(
            "preferences_updated",
            user_id=str(current_user.id),
            updated_fields=list(updates.keys()),
        )

        return PreferencesResponse(**updated_preferences)

    except ValueError as e:
        logger.error(
            "update_preferences_failed",
            user_id=str(current_user.id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            "update_preferences_error",
            user_id=str(current_user.id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update preferences",
        )
