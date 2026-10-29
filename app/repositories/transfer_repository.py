
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Transfer, Wallet


def create_transfer(db: Session, transfer: Transfer) -> Transfer:
    db.add(transfer)
    db.flush()
    return transfer


def get_transfer_by_id(db: Session, transfer_id: int) -> Transfer | None:
    return db.scalar(
        select(Transfer).where(Transfer.id == transfer_id)
    )


def get_transfer_by_reference(
    db: Session,
    reference: str,
) -> Transfer | None:
    return db.scalar(
        select(Transfer).where(Transfer.reference == reference)
    )


def list_transfers_for_wallets(
    db: Session,
    wallet_ids: list[int],
    limit: int = 50,
    offset: int = 0,
) -> list[Transfer]:
    if not wallet_ids:
        return []

    statement = (
        select(Transfer)
        .where(
            (Transfer.sender_wallet_id.in_(wallet_ids))
            | (Transfer.receiver_wallet_id.in_(wallet_ids))
        )
        .order_by(Transfer.created_at.desc(), Transfer.id.desc())
        .limit(limit)
        .offset(offset)
    )

    return list(db.scalars(statement).all())


def lock_wallets(
    db: Session,
    wallet_ids: list[int],
) -> list[Wallet]:
    if not wallet_ids:
        return []

    statement = (
        select(Wallet)
        .where(Wallet.id.in_(sorted(set(wallet_ids))))
        .order_by(Wallet.id)
        .with_for_update()
    )

    return list(db.scalars(statement).all())
