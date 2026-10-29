
import getpass

from sqlalchemy import select, text

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Role, User


def main() -> None:
    email = input("Super Admin email: ").strip().lower()
    full_name = input("Super Admin full name: ").strip()

    if not email or "@" not in email:
        raise SystemExit("Enter a valid email address.")

    if len(full_name) < 2 or len(full_name) > 150:
        raise SystemExit("Name must contain 2–150 characters.")

    password = getpass.getpass("Super Admin password (12+ characters): ")
    confirmation = getpass.getpass("Confirm password: ")

    if len(password) < 12 or len(password) > 128:
        raise SystemExit("Password must contain 12–128 characters.")

    if password != confirmation:
        raise SystemExit("Passwords do not match.")

    with SessionLocal() as db:
        try:
            # PostgreSQL transaction-level lock prevents concurrent
            # executions of this bootstrap script.
            db.execute(text("SELECT pg_advisory_xact_lock(918274631)"))

            existing_super_admin = db.scalar(
                select(User.id)
                .join(User.roles)
                .where(Role.name == "SUPER_ADMIN")
                .limit(1)
            )

            if existing_super_admin is not None:
                raise SystemExit(
                    "A Super Admin already exists. Bootstrap refused."
                )

            existing_user = db.scalar(
                select(User.id).where(User.email == email)
            )

            if existing_user is not None:
                raise SystemExit(
                    "This email already belongs to a user. "
                    "Use a different email."
                )

            role = db.scalar(
                select(Role).where(Role.name == "SUPER_ADMIN")
            )

            if role is None:
                raise SystemExit(
                    "SUPER_ADMIN role is missing. Run the role-seeding "
                    "script before creating the account."
                )

            user = User(
                email=email,
                full_name=full_name,
                password_hash=hash_password(password),
                is_active=True,
            )
            user.roles.append(role)

            db.add(user)
            db.commit()

            print("Super Admin created successfully.")
            print(f"User ID: {user.id}")
            print(f"Email: {user.email}")
            print("Role: SUPER_ADMIN")

        except Exception:
            db.rollback()
            raise


if __name__ == "__main__":
    main()
