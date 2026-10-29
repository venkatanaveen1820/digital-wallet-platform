
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.deposit import (
    DepositCreateRequest,
    DepositResponse,
)
from app.services import deposit_service


router = APIRouter(tags=["Deposits"])


@router.post(
    "/wallets/{wallet_id}/deposits",
    response_model=DepositResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_deposit(
    wallet_id: int,
    data: DepositCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return deposit_service.create_deposit(
        db, current_user, wallet_id, data
    )


@router.get(
    "/deposits",
    response_model=list[DepositResponse],
)
def list_deposits(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return deposit_service.list_deposits(db, current_user)


@router.get(
    "/deposits/{deposit_id}",
    response_model=DepositResponse,
)
def get_deposit(
    deposit_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return deposit_service.get_deposit(
        db, current_user, deposit_id
    )
