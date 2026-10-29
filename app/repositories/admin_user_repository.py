
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import User


def get_by_id(db: Session, user_id: int) -> User | None:
    return db.scalar(
        select(User)
        .options(selectinload(User.roles))
        .where(User.id == user_id)
    )


def list_users(
    db: Session,
    offset: int = 0,
    limit: int = 50,
) -> list[User]:
    statement = (
        select(User)
        .options(selectinload(User.roles))
        .order_by(User.id)
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(statement).all())
