
from getpass import getpass

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import User


EMAIL = "wallet.test@example.com"


def main():
    new_password = getpass("Enter the new password: ")
    confirm_password = getpass("Confirm the new password: ")

    if len(new_password) < 12:
        print("Password must contain at least 12 characters.")
        return

    if new_password != confirm_password:
        print("Passwords do not match.")
        return

    with SessionLocal() as db:
        user = db.scalar(
            select(User).where(User.email == EMAIL)
        )

        if user is None:
            print(f"User not found: {EMAIL}")
            return

        user.password_hash = hash_password(new_password)
        db.commit()

        print(f"Password reset successfully for {EMAIL}.")


if __name__ == "__main__":
    main()
