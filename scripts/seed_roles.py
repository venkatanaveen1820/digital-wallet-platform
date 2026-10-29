
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Role

ROLE_NAMES = [
    "SUPER_ADMIN",
    "ADMIN",
    "SUPPORT_AGENT",
    "CUSTOMER",
]


def seed_roles() -> None:
    with SessionLocal() as db:
        try:
            for name in ROLE_NAMES:
                role = db.scalar(
                    select(Role).where(Role.name == name)
                )

                if role is None:
                    db.add(Role(name=name))

            db.commit()
            print("Roles seeded successfully.")

        except Exception:
            db.rollback()
            raise


if __name__ == "__main__":
    seed_roles()
