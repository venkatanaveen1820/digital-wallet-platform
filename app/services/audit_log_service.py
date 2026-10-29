from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import User
from app.repositories.audit_log_repository import AuditLogRepository


def create_audit_log(
    db: Session,
    *,
    user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    ip_address: str | None = None,
    metadata: dict | None = None,
):
    """
    Add an audit record to the current transaction.

    This function deliberately does not commit.
    The calling service owns the transaction.
    """
    return AuditLogRepository.create(
        db,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        ip_address=ip_address,
        metadata=metadata,
    )


def list_audit_logs(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    user_id: int | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    from_timestamp: datetime | None = None,
    to_timestamp: datetime | None = None,
) -> dict:
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Page must be at least 1.",
        )

    if not 1 <= page_size <= 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Page size must be between 1 and 100.",
        )

    if (
        from_timestamp is not None
        and to_timestamp is not None
        and from_timestamp > to_timestamp
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "from_timestamp must be before or equal to to_timestamp."
            ),
        )

    filters = {
        "user_id": user_id,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "from_timestamp": from_timestamp,
        "to_timestamp": to_timestamp,
    }

    items = AuditLogRepository.list_logs(
        db,
        offset=(page - 1) * page_size,
        limit=page_size,
        **filters,
    )

    total = AuditLogRepository.count_logs(
        db,
        **filters,
    )

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
    }


def get_audit_log(
    db: Session,
    audit_log_id: int,
):
    audit_log = AuditLogRepository.get_by_id(
        db,
        audit_log_id,
    )

    if audit_log is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log not found.",
        )

    return audit_log


def list_my_audit_logs(
    db: Session,
    current_user: User,
    *,
    page: int = 1,
    page_size: int = 20,
    action: str | None = None,
    entity_type: str | None = None,
    from_timestamp: datetime | None = None,
    to_timestamp: datetime | None = None,
) -> dict:
    # Derive the user ID from the authenticated identity.
    # Never accept it from the caller for this endpoint.
    return list_audit_logs(
        db,
        page=page,
        page_size=page_size,
        user_id=current_user.id,
        action=action,
        entity_type=entity_type,
        from_timestamp=from_timestamp,
        to_timestamp=to_timestamp,
    )