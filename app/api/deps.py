
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User


bearer_scheme = HTTPBearer(
    auto_error=False,
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db),
) -> User:
    """Validate the access token and return the authenticated user."""

    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_error

    try:
        payload = decode_access_token(credentials.credentials)

        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject.isdigit():
            raise ValueError("Invalid token subject")

        user_id = int(subject)
        if user_id <= 0:
            raise ValueError("Invalid user ID")

    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise credentials_error from None

    user = db.scalar(
        select(User).where(User.id == user_id)
    )

    if user is None:
        raise credentials_error

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive.",
        )

    return user


def require_roles(*allowed_roles: str):
    """Restrict an endpoint to users with at least one allowed role."""

    allowed = set(allowed_roles)

    def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        user_roles = {role.name for role in current_user.roles}

        if not user_roles.intersection(allowed):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )

        return current_user

    return role_checker
