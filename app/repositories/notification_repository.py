from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.notification import Notification


class NotificationRepository:

    @staticmethod
    def create(
        db: Session,
        *,
        user_id: int,
        event_type: str,
        title: str,
        message: str,
        entity_type: str | None = None,
        entity_id: int | None = None,
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            event_type=event_type,
            title=title,
            message=message,
            entity_type=entity_type,
            entity_id=entity_id,
        )

        db.add(notification)
        db.flush()

        return notification

    @staticmethod
    def get_by_id(
        db: Session,
        notification_id: int,
    ) -> Notification | None:
        return db.get(Notification, notification_id)

    @staticmethod
    def get_for_user(
        db: Session,
        *,
        notification_id: int,
        user_id: int,
        lock: bool = False,
    ) -> Notification | None:
        statement = select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )

        if lock:
            statement = statement.with_for_update()

        return db.scalar(statement)

    @staticmethod
    def list_for_user(
        db: Session,
        *,
        user_id: int,
        offset: int,
        limit: int,
        unread_only: bool = False,
    ) -> list[Notification]:
        statement = select(Notification).where(
            Notification.user_id == user_id
        )

        if unread_only:
            statement = statement.where(
                Notification.is_read.is_(False)
            )

        statement = (
            statement
            .order_by(
                Notification.created_at.desc(),
                Notification.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        return list(db.scalars(statement).all())

    @staticmethod
    def count_for_user(
        db: Session,
        *,
        user_id: int,
        unread_only: bool = False,
    ) -> int:
        statement = select(func.count()).select_from(
            Notification
        ).where(
            Notification.user_id == user_id
        )

        if unread_only:
            statement = statement.where(
                Notification.is_read.is_(False)
            )

        return db.scalar(statement) or 0

    @staticmethod
    def mark_read(
        db: Session,
        notification: Notification,
        read_at: datetime,
    ) -> Notification:
        notification.is_read = True
        notification.read_at = read_at

        db.flush()

        return notification

    @staticmethod
    def mark_all_read(
        db: Session,
        *,
        user_id: int,
        read_at: datetime,
    ) -> int:
        statement = (
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
            .values(
                is_read=True,
                read_at=read_at,
            )
        )

        result = db.execute(statement)

        return result.rowcount or 0