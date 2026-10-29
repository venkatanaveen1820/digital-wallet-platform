from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.user import User
from app.repositories.notification_repository import (
    NotificationRepository,
)


def create_notification(
    db: Session,
    *,
    user_id: int,
    event_type: str,
    title: str,
    message: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
) -> Notification:
    """
    Add a notification to the current transaction.

    Deliberately does not commit. The calling financial
    service commits the notification with the business operation.
    """
    return NotificationRepository.create(
        db,
        user_id=user_id,
        event_type=event_type,
        title=title,
        message=message,
        entity_type=entity_type,
        entity_id=entity_id,
    )


def list_notifications(
    db: Session,
    user: User,
    *,
    page: int = 1,
    page_size: int = 20,
    unread_only: bool = False,
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

    offset = (page - 1) * page_size

    items = NotificationRepository.list_for_user(
        db,
        user_id=user.id,
        offset=offset,
        limit=page_size,
        unread_only=unread_only,
    )

    total = NotificationRepository.count_for_user(
        db,
        user_id=user.id,
        unread_only=unread_only,
    )

    unread_count = NotificationRepository.count_for_user(
        db,
        user_id=user.id,
        unread_only=True,
    )

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "unread_count": unread_count,
    }


def mark_notification_read(
    db: Session,
    user: User,
    notification_id: int,
) -> Notification:
    notification = NotificationRepository.get_for_user(
        db,
        notification_id=notification_id,
        user_id=user.id,
        lock=True,
    )

    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        )

    if notification.is_read:
        return notification

    try:
        NotificationRepository.mark_read(
            db,
            notification,
            datetime.now(timezone.utc),
        )

        db.commit()
        db.refresh(notification)

        return notification

    except Exception:
        db.rollback()
        raise


def mark_all_notifications_read(
    db: Session,
    user: User,
) -> dict:
    try:
        updated_count = NotificationRepository.mark_all_read(
            db,
            user_id=user.id,
            read_at=datetime.now(timezone.utc),
        )

        db.commit()

        return {"updated_count": updated_count}

    except Exception:
        db.rollback()
        raise