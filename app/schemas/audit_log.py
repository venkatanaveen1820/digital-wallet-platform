from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditLogResponse(BaseModel):
    id: int
    user_id: int | None
    action: str
    entity_type: str
    entity_id: int | None
    timestamp: datetime
    ip_address: str | None
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="metadata_json",
    )

    model_config = ConfigDict(from_attributes=True)


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    page: int
    page_size: int
    total: int