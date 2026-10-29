from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    event_type: str
    title: str
    message: str
    is_read: bool
    entity_type: str | None = None
    entity_id: int | None = None
    created_at: datetime
    read_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    page: int
    page_size: int
    total: int
    unread_count: int


class MarkAllReadResponse(BaseModel):
    updated_count: int = Field(ge=0)