
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models import RefreshToken, User
from app.repositories import (
    refresh_token_repository,
    role_repository,
    user_repository,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _get_user_response(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "roles": [role.name for role in user.roles],
    }


def _issue_tokens(db: Session, user: User) -> dict:
    raw_refresh_token = generate_refresh_token()

    refresh_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(raw_refresh_token),
        expires_at=_utc_now()
        + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )

    refresh_token_repository.add(db, refresh_record)

    return {
        "access_token": create_access_token(user.id),
        "refresh_token": raw_refresh_token,
        "token_type": "bearer",
    }


def register_user(db: Session, data) -> dict:
    email = str(data.email).strip().lower()

    if user_repository.get_by_email(db, email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    customer_role = role_repository.get_by_name(db, "CUSTOMER")
    if customer_role is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Default customer role is not configured.",
        )

    user = User(
        email=email,
        full_name=data.full_name.strip(),
        password_hash=hash_password(data.password),
        is_active=True,
    )
    user.roles.append(customer_role)

    try:
        user_repository.add(db, user)
        result = _get_user_response(user)
        db.commit()
        return result
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        ) from exc


def login_user(db: Session, data) -> dict:
    email = str(data.email).strip().lower()
    user = user_repository.get_by_email(db, email)

    if user is None or not verify_password(
        data.password, user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive.",
        )

    try:
        tokens = _issue_tokens(db, user)
        db.commit()
        return {
            **tokens,
            "user": _get_user_response(user),
        }
    except Exception:
        db.rollback()
        raise


def refresh_user_tokens(db: Session, raw_token: str) -> dict:
    token_hash = hash_refresh_token(raw_token)

    try:
        record = refresh_token_repository.get_by_hash_for_update(
            db, token_hash
        )

        now = _utc_now()

        if (
            record is None
            or record.revoked_at is not None
            or record.expires_at <= now
        ):
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token is invalid, expired, or revoked.",
            )

        user = user_repository.get_by_id(db, record.user_id)

        if user is None or not user.is_active:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is unavailable.",
            )

        record.revoked_at = now
        tokens = _issue_tokens(db, user)
        db.commit()
        return tokens

    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise


def logout_user(db: Session, user_id: int, raw_token: str) -> None:
    try:
        record = refresh_token_repository.get_by_hash_for_update(
            db, hash_refresh_token(raw_token)
        )

        if (
            record is not None
            and record.user_id == user_id
            and record.revoked_at is None
        ):
            record.revoked_at = _utc_now()
            db.commit()
    except Exception:
        db.rollback()
        raise


def change_user_password(
    db: Session,
    user: User,
    current_password: str,
    new_password: str,
) -> None:
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    if verify_password(new_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must differ from the current password.",
        )

    try:
        user.password_hash = hash_password(new_password)

        refresh_token_repository.revoke_active_tokens(
            db, user.id, _utc_now()
        )

        db.commit()
    except Exception:
        db.rollback()
        raise
