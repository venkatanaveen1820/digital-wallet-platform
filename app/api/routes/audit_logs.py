from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models import User
from app.schemas.audit_log import (
    AuditLogListResponse,
    AuditLogResponse,
)
from app.services import audit_log_service

router = APIRouter(
    prefix="/audit-logs",
    tags=["Audit Logs"],
)


@router.get(
    "/me",
    response_model=AuditLogListResponse,
)
def get_my_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    action: str | None = Query(None, min_length=1, max_length=60),
    entity_type: str | None = Query(None, min_length=1, max_length=60),
    from_timestamp: datetime | None = Query(None),
    to_timestamp: datetime | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return audit_log_service.list_my_audit_logs(
        db,
        current_user,
        page=page,
        page_size=page_size,
        action=action,
        entity_type=entity_type,
        from_timestamp=from_timestamp,
        to_timestamp=to_timestamp,
    )


@router.get(
    "",
    response_model=AuditLogListResponse,
)
def get_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: int | None = Query(None, ge=1),
    action: str | None = Query(None, min_length=1, max_length=60),
    entity_type: str | None = Query(None, min_length=1, max_length=60),
    entity_id: int | None = Query(None, ge=1),
    from_timestamp: datetime | None = Query(None),
    to_timestamp: datetime | None = Query(None),
    current_user: User = Depends(
        require_roles("SUPER_ADMIN", "ADMIN")
    ),
    db: Session = Depends(get_db),
):
    return audit_log_service.list_audit_logs(
        db,
        page=page,
        page_size=page_size,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        from_timestamp=from_timestamp,
        to_timestamp=to_timestamp,
    )


@router.get(
    "/{audit_log_id}",
    response_model=AuditLogResponse,
)
def get_audit_log_by_id(
    audit_log_id: int,
    current_user: User = Depends(
        require_roles("SUPER_ADMIN", "ADMIN")
    ),
    db: Session = Depends(get_db),
):
    return audit_log_service.get_audit_log(
        db,
        audit_log_id,
    )