"""
Privacy and data management schemas for request/response validation.
"""
from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel


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
