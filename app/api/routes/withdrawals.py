
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.withdrawal import (
    WithdrawalCreateRequest,
    WithdrawalResponse,
)
from app.services import withdrawal_service


router = APIRouter(tags=["Withdrawals"])


@router.post(
    "/wallets/{wallet_id}/withdrawals",
    response_model=WithdrawalResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_withdrawal(
    wallet_id: int,
    data: WithdrawalCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return withdrawal_service.create_withdrawal(
        db, current_user, wallet_id, data
    )


@router.get(
    "/withdrawals",
    response_model=list[WithdrawalResponse],
)
def list_withdrawals(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return withdrawal_service.list_withdrawals(db, current_user)


@router.get(
    "/withdrawals/{withdrawal_id}",
    response_model=WithdrawalResponse,
)
def get_withdrawal(
    withdrawal_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return withdrawal_service.get_withdrawal(
        db, current_user, withdrawal_id
    )


@router.post(
    "/withdrawals/{withdrawal_id}/cancel",
    response_model=WithdrawalResponse,
)
def cancel_withdrawal(
    withdrawal_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return withdrawal_service.cancel_withdrawal(
        db, current_user, withdrawal_id
    )
