"""
Privacy and data management schemas for request/response validation.
"""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ============================================================================
# Request Schemas
# ============================================================================


class PreferencesUpdateRequest(BaseModel):
    """Privacy preferences update request."""
    analytics_consent: Optional[bool] = Field(None, description="Consent for analytics and tracking")
    email_notifications: Optional[bool] = Field(None, description="Enable email notifications")
    trade_confirmations: Optional[bool] = Field(None, description="Email confirmations for trades")
    marketing_emails: Optional[bool] = Field(None, description="Receive marketing emails")
    theme: Optional[Literal["light", "dark"]] = Field(None, description="UI theme preference")


# ============================================================================
# Response Schemas
# ============================================================================


class DataExportResponse(BaseModel):
    """User data export response."""
    export_metadata: Dict[str, Any]
    profile: Dict[str, Any]
    security: Dict[str, Any]
    permissions: Dict[str, Any]
    preferences: Dict[str, Any]
    sessions: List[Dict[str, Any]]
    audit_logs: List[Dict[str, Any]]


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str


class PreferencesResponse(BaseModel):
    """Privacy preferences response."""
    analytics_consent: bool = Field(..., description="Consent for analytics and tracking")
    email_notifications: bool = Field(..., description="Enable email notifications")
    trade_confirmations: bool = Field(..., description="Email confirmations for trades")
    marketing_emails: bool = Field(..., description="Receive marketing emails")
    theme: Literal["light", "dark"] = Field(..., description="UI theme preference")
