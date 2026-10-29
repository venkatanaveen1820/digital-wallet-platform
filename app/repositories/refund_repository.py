from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Refund


# These statuses reserve part of the original transfer amount. Rejected and failed
# requests release their reservation so the customer can submit another request.
RESERVED_STATUSES = ("REQUESTED", "UNDER_REVIEW", "APPROVED", "COMPLETED")


def add(db: Session, refund: Refund) -> Refund:
    db.add(refund)
    db.flush()
    return refund


def get_by_id(db: Session, refund_id: int, *, for_update: bool = False) -> Refund | None:
    statement = select(Refund).where(Refund.id == refund_id)
    if for_update:
        statement = statement.with_for_update()
    return db.scalar(statement)


def list_all(db: Session) -> list[Refund]:
    statement = select(Refund).order_by(Refund.created_at.desc(), Refund.id.desc())
    return list(db.scalars(statement).all())


def list_for_user(db: Session, user_id: int) -> list[Refund]:
    statement = (
        select(Refund)
        .where(Refund.requested_by == user_id)
        .order_by(Refund.created_at.desc(), Refund.id.desc())
    )
    return list(db.scalars(statement).all())


def sum_reserved_for_transfer(db: Session, transfer_id: int) -> Decimal:
    statement = select(func.coalesce(func.sum(Refund.amount), 0)).where(
        Refund.transfer_id == transfer_id,
        Refund.status.in_(RESERVED_STATUSES),
    )
    return Decimal(db.scalar(statement) or 0)
