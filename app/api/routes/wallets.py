
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models import User
from app.schemas.wallet import (
    WalletCreateRequest,
    WalletResponse,
    WalletStatusUpdateRequest,
)
from app.services import wallet_service


router = APIRouter(
    prefix="/wallets",
    tags=["Wallets"],
)


@router.post(
    "",
    response_model=WalletResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_wallet(
    data: WalletCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return wallet_service.create_wallet(db, current_user, data)


@router.get(
    "",
    response_model=list[WalletResponse],
)
def list_my_wallets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return wallet_service.list_my_wallets(db, current_user)


@router.get(
    "/{wallet_id}",
    response_model=WalletResponse,
)
def get_my_wallet(
    wallet_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return wallet_service.get_my_wallet(
        db, current_user, wallet_id
    )


@router.patch(
    "/{wallet_id}",
    response_model=WalletResponse,
)
def update_wallet_status(
    wallet_id: int,
    data: WalletStatusUpdateRequest,
    current_user: User = Depends(
        require_roles("SUPER_ADMIN", "ADMIN")
    ),
    db: Session = Depends(get_db),
):
    return wallet_service.update_wallet_status(
        db, current_user, wallet_id, data.status
    )


@router.post(
    "/{wallet_id}/freeze",
    response_model=WalletResponse,
)
def freeze_wallet(
    wallet_id: int,
    current_user: User = Depends(
        require_roles("SUPER_ADMIN", "ADMIN")
    ),
    db: Session = Depends(get_db),
):
    return wallet_service.update_wallet_status(
        db, current_user, wallet_id, "FROZEN"
    )


@router.post(
    "/{wallet_id}/unfreeze",
    response_model=WalletResponse,
)
def unfreeze_wallet(
    wallet_id: int,
    current_user: User = Depends(
        require_roles("SUPER_ADMIN", "ADMIN")
    ),
    db: Session = Depends(get_db),
):
    return wallet_service.update_wallet_status(
        db, current_user, wallet_id, "ACTIVE"
    )
