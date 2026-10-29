
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Deposit


def add(db: Session, deposit: Deposit) -> Deposit:
    db.add(deposit)
    db.flush()
    return deposit


def get_by_id(db: Session, deposit_id: int) -> Deposit | None:
    return db.scalar(
        select(Deposit).where(Deposit.id == deposit_id)
    )


def list_for_wallets(
    db: Session,
    wallet_ids: list[int],
) -> list[Deposit]:
    if not wallet_ids:
        return []

    statement = (
        select(Deposit)
        .where(Deposit.wallet_id.in_(wallet_ids))
        .order_by(Deposit.created_at.desc(), Deposit.id.desc())
    )
    return list(db.scalars(statement).all())
