
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models import User
from app.schemas.admin import (
    AdminCreateUserRequest,
    AdminUpdateUserRequest,
    ChangeUserRoleRequest,
    UserAdminResponse,
)
from app.services import admin_user_service


router = APIRouter(
    prefix="/admin/users",
    tags=["User Administration"],
)


@router.get("", response_model=list[UserAdminResponse])
def list_users(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(
        require_roles("SUPER_ADMIN", "ADMIN")
    ),
    db: Session = Depends(get_db),
):
    return admin_user_service.list_users(
        db, current_user, offset, limit
    )


@router.get("/{user_id}", response_model=UserAdminResponse)
def get_user(
    user_id: int,
    current_user: User = Depends(
        require_roles("SUPER_ADMIN", "ADMIN")
    ),
    db: Session = Depends(get_db),
):
    return admin_user_service.get_user(
        db, current_user, user_id
    )


@router.post(
    "",
    response_model=UserAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    data: AdminCreateUserRequest,
    current_user: User = Depends(
        require_roles("SUPER_ADMIN", "ADMIN")
    ),
    db: Session = Depends(get_db),
):
    return admin_user_service.create_user(
        db, current_user, data
    )


@router.patch("/{user_id}", response_model=UserAdminResponse)
def update_user(
    user_id: int,
    data: AdminUpdateUserRequest,
    current_user: User = Depends(
        require_roles("SUPER_ADMIN", "ADMIN")
    ),
    db: Session = Depends(get_db),
):
    return admin_user_service.update_user(
        db, current_user, user_id, data
    )


@router.patch(
    "/{user_id}/role",
    response_model=UserAdminResponse,
)
def change_user_role(
    user_id: int,
    data: ChangeUserRoleRequest,
    current_user: User = Depends(
        require_roles("SUPER_ADMIN", "ADMIN")
    ),
    db: Session = Depends(get_db),
):
    return admin_user_service.change_user_role(
        db, current_user, user_id, data
    )


@router.post(
    "/{user_id}/activate",
    response_model=UserAdminResponse,
)
def activate_user(
    user_id: int,
    current_user: User = Depends(
        require_roles("SUPER_ADMIN", "ADMIN")
    ),
    db: Session = Depends(get_db),
):
    return admin_user_service.activate_user(
        db, current_user, user_id
    )


@router.post(
    "/{user_id}/deactivate",
    response_model=UserAdminResponse,
)
def deactivate_user(
    user_id: int,
    current_user: User = Depends(
        require_roles("SUPER_ADMIN", "ADMIN")
    ),
    db: Session = Depends(get_db),
):
    return admin_user_service.deactivate_user(
        db, current_user, user_id
    )
