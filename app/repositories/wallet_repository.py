
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Wallet


def add(db: Session, wallet: Wallet) -> Wallet:
    db.add(wallet)
    db.flush()
    return wallet


def get_by_id(db: Session, wallet_id: int) -> Wallet | None:
    return db.scalar(
        select(Wallet).where(Wallet.id == wallet_id)
    )


def get_owned_wallet(
    db: Session,
    wallet_id: int,
    user_id: int,
) -> Wallet | None:
    return db.scalar(
        select(Wallet).where(
            Wallet.id == wallet_id,
            Wallet.user_id == user_id,
        )
    )


def list_owned_wallets(
    db: Session,
    user_id: int,
) -> list[Wallet]:
    statement = (
        select(Wallet)
        .where(Wallet.user_id == user_id)
        .order_by(Wallet.id)
    )
    return list(db.scalars(statement).all())
