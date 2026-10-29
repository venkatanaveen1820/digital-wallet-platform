from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


class AuditLogRepository:

    @staticmethod
    def create(
        db: Session,
        *,
        user_id: int | None,
        action: str,
        entity_type: str,
        entity_id: int | None = None,
        ip_address: str | None = None,
        metadata: dict | None = None,
    ) -> AuditLog:
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            ip_address=ip_address,
            metadata_json=metadata or {},
        )

        db.add(audit_log)
        db.flush()

        return audit_log

    @staticmethod
    def get_by_id(
        db: Session,
        audit_log_id: int,
    ) -> AuditLog | None:
        return db.get(AuditLog, audit_log_id)

    @staticmethod
    def list_logs(
        db: Session,
        *,
        offset: int = 0,
        limit: int = 20,
        user_id: int | None = None,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        from_timestamp: datetime | None = None,
        to_timestamp: datetime | None = None,
    ) -> list[AuditLog]:
        statement = select(AuditLog)

        if user_id is not None:
            statement = statement.where(
                AuditLog.user_id == user_id
            )

        if action is not None:
            statement = statement.where(
                AuditLog.action == action
            )

        if entity_type is not None:
            statement = statement.where(
                AuditLog.entity_type == entity_type
            )

        if entity_id is not None:
            statement = statement.where(
                AuditLog.entity_id == entity_id
            )

        if from_timestamp is not None:
            statement = statement.where(
                AuditLog.timestamp >= from_timestamp
            )

        if to_timestamp is not None:
            statement = statement.where(
                AuditLog.timestamp <= to_timestamp
            )

        statement = (
            statement
            .order_by(
                AuditLog.timestamp.desc(),
                AuditLog.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        return list(db.scalars(statement).all())

    @staticmethod
    def count_logs(
        db: Session,
        *,
        user_id: int | None = None,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        from_timestamp: datetime | None = None,
        to_timestamp: datetime | None = None,
    ) -> int:
        statement = select(func.count()).select_from(AuditLog)

        if user_id is not None:
            statement = statement.where(
                AuditLog.user_id == user_id
            )

        if action is not None:
            statement = statement.where(
                AuditLog.action == action
            )

        if entity_type is not None:
            statement = statement.where(
                AuditLog.entity_type == entity_type
            )

        if entity_id is not None:
            statement = statement.where(
                AuditLog.entity_id == entity_id
            )

        if from_timestamp is not None:
            statement = statement.where(
                AuditLog.timestamp >= from_timestamp
            )

        if to_timestamp is not None:
            statement = statement.where(
                AuditLog.timestamp <= to_timestamp
            )

        return db.scalar(statement) or 0