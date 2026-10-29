
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Role


def get_by_name(db: Session, name: str) -> Role | None:
    return db.scalar(
        select(Role).where(Role.name == name)
    )
