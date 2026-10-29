
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Withdrawal


def add(db: Session, withdrawal: Withdrawal) -> Withdrawal:
    db.add(withdrawal)
    db.flush()
    return withdrawal


def get_by_id(
    db: Session,
    withdrawal_id: int,
    *,
    for_update: bool = False,
) -> Withdrawal | None:
    statement = select(Withdrawal).where(
        Withdrawal.id == withdrawal_id
    )

    if for_update:
        statement = statement.with_for_update()

    return db.scalar(statement)


def get_by_reference(
    db: Session,
    reference_number: str,
) -> Withdrawal | None:
    return db.scalar(
        select(Withdrawal).where(
            Withdrawal.reference_number == reference_number
        )
    )


def list_for_wallets(
    db: Session,
    wallet_ids: list[int],
) -> list[Withdrawal]:
    if not wallet_ids:
        return []

    statement = (
        select(Withdrawal)
        .where(Withdrawal.wallet_id.in_(wallet_ids))
        .order_by(
            Withdrawal.created_at.desc(),
            Withdrawal.id.desc(),
        )
    )

    return list(db.scalars(statement).all())


def list_all(db: Session) -> list[Withdrawal]:
    statement = select(Withdrawal).order_by(
        Withdrawal.created_at.desc(),
        Withdrawal.id.desc(),
    )

    return list(db.scalars(statement).all())


def sum_completed_for_wallet_since(
    db: Session,
    wallet_id: int,
    start_time,
    end_time,
):
    statement = select(
        func.coalesce(func.sum(Withdrawal.amount), 0)
    ).where(
        Withdrawal.wallet_id == wallet_id,
        Withdrawal.status == "COMPLETED",
        Withdrawal.created_at >= start_time,
        Withdrawal.created_at < end_time,
    )

    return db.scalar(statement)


def count_completed_for_wallet_since(
    db: Session,
    wallet_id: int,
    start_time,
    end_time,
) -> int:
    statement = select(func.count(Withdrawal.id)).where(
        Withdrawal.wallet_id == wallet_id,
        Withdrawal.status == "COMPLETED",
        Withdrawal.created_at >= start_time,
        Withdrawal.created_at < end_time,
    )

    return db.scalar(statement) or 0
