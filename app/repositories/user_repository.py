
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


def get_by_id(db: Session, user_id: int) -> User | None:
    return db.scalar(
        select(User).where(User.id == user_id)
    )


def get_by_email(db: Session, email: str) -> User | None:
    normalized_email = email.strip().lower()
    return db.scalar(
        select(User).where(User.email == normalized_email)
    )


def add(db: Session, user: User) -> User:
    db.add(user)
    db.flush()
    return user
