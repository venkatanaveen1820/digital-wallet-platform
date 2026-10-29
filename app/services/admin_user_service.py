
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import User
from app.repositories import (
    admin_user_repository,
    role_repository,
    user_repository,
)


ALLOWED_ROLES = {
    "SUPER_ADMIN",
    "ADMIN",
    "SUPPORT_AGENT",
    "CUSTOMER",
}


def _role_names(user: User) -> set[str]:
    return {role.name for role in user.roles}


def _user_response(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "roles": sorted(_role_names(user)),
    }


def _require_role_assignment_permission(
    actor: User,
    requested_role: str,
) -> None:
    actor_roles = _role_names(actor)

    if "SUPER_ADMIN" in actor_roles:
        return

    if "ADMIN" in actor_roles and requested_role in {
        "CUSTOMER",
        "SUPPORT_AGENT",
    }:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You are not authorized to assign this role.",
    )


def _require_target_management_permission(
    actor: User,
    target: User,
) -> None:
    actor_roles = _role_names(actor)
    target_roles = _role_names(target)

    if "SUPER_ADMIN" in actor_roles:
        return

    if "ADMIN" not in actor_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to manage users.",
        )

    if target_roles.intersection({"SUPER_ADMIN", "ADMIN"}):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins cannot manage Super Admin or Admin accounts.",
        )


def list_users(
    db: Session,
    actor: User,
    offset: int = 0,
    limit: int = 50,
) -> list[dict]:
    if not _role_names(actor).intersection({"SUPER_ADMIN", "ADMIN"}):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to list users.",
        )

    users = admin_user_repository.list_users(
        db,
        offset=max(offset, 0),
        limit=min(max(limit, 1), 100),
    )
    return [_user_response(user) for user in users]


def get_user(
    db: Session,
    actor: User,
    target_user_id: int,
) -> dict:
    target = admin_user_repository.get_by_id(db, target_user_id)

    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    _require_target_management_permission(actor, target)
    return _user_response(target)


def create_user(
    db: Session,
    actor: User,
    data,
) -> dict:
    requested_role = data.role.strip().upper()

    if requested_role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unknown role.",
        )

    _require_role_assignment_permission(actor, requested_role)

    email = str(data.email).strip().lower()

    if user_repository.get_by_email(db, email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    role = role_repository.get_by_name(db, requested_role)

    if role is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The requested role is not configured.",
        )

    user = User(
        email=email,
        full_name=data.full_name.strip(),
        password_hash=hash_password(data.password),
        is_active=True,
    )
    user.roles.append(role)

    try:
        user_repository.add(db, user)
        db.flush()
        result = _user_response(user)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def update_user(
    db: Session,
    actor: User,
    target_user_id: int,
    data,
) -> dict:
    target = admin_user_repository.get_by_id(db, target_user_id)

    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    _require_target_management_permission(actor, target)

    if data.full_name is not None:
        target.full_name = data.full_name.strip()

    try:
        db.flush()
        result = _user_response(target)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def change_user_role(
    db: Session,
    actor: User,
    target_user_id: int,
    data,
) -> dict:
    target = admin_user_repository.get_by_id(db, target_user_id)

    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    _require_target_management_permission(actor, target)

    if target.id == actor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot change your own role.",
        )

    requested_role = data.role.strip().upper()

    if requested_role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unknown role.",
        )

    _require_role_assignment_permission(actor, requested_role)

    role = role_repository.get_by_name(db, requested_role)

    if role is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The requested role is not configured.",
        )

    try:
        target.roles.clear()
        target.roles.append(role)
        db.flush()
        result = _user_response(target)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def set_user_active_status(
    db: Session,
    actor: User,
    target_user_id: int,
    is_active: bool,
) -> dict:
    target = admin_user_repository.get_by_id(db, target_user_id)

    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    _require_target_management_permission(actor, target)

    if target.id == actor.id and not is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot deactivate your own account.",
        )

    try:
        target.is_active = is_active
        db.flush()
        result = _user_response(target)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def activate_user(
    db: Session,
    actor: User,
    target_user_id: int,
) -> dict:
    return set_user_active_status(
        db, actor, target_user_id, True
    )


def deactivate_user(
    db: Session,
    actor: User,
    target_user_id: int,
) -> dict:
    return set_user_active_status(
        db, actor, target_user_id, False
    )
