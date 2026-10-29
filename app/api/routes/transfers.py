
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Transfer, User, Wallet
from app.schemas.transfer import TransferCreateRequest, TransferResponse
from app.services import transfer_service


router = APIRouter(prefix="/transfers", tags=["Transfers"])


@router.post(
    "",
    response_model=TransferResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_transfer(
    data: TransferCreateRequest,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=255),
    ],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return transfer_service.create_transfer(
        db,
        current_user,
        data,
        idempotency_key,
    )


@router.get("", response_model=list[TransferResponse])
def list_transfers(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Customers see transfers involving their own wallets.
    # Privileged roles can view all transfers.
    privileged_roles = {"SUPER_ADMIN", "ADMIN", "SUPPORT_AGENT"}
    if any(role.name in privileged_roles for role in current_user.roles):
        statement = select(Transfer)
    else:
        wallet_ids = list(
            db.scalars(
                select(Wallet.id).where(Wallet.user_id == current_user.id)
            ).all()
        )
        if not wallet_ids:
            return []

        statement = select(Transfer).where(
            (Transfer.sender_wallet_id.in_(wallet_ids))
            | (Transfer.receiver_wallet_id.in_(wallet_ids))
        )

    statement = (
        statement
        .order_by(Transfer.created_at.desc(), Transfer.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(statement).all())


@router.get("/{transfer_id}", response_model=TransferResponse)
def get_transfer(
    transfer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    transfer = db.get(Transfer, transfer_id)

    if transfer is None:
        raise HTTPException(status_code=404, detail="Transfer not found.")

    privileged_roles = {"SUPER_ADMIN", "ADMIN", "SUPPORT_AGENT"}
    is_privileged = any(
        role.name in privileged_roles for role in current_user.roles
    )

    if not is_privileged:
        wallet_ids = set(
            db.scalars(
                select(Wallet.id).where(Wallet.user_id == current_user.id)
            ).all()
        )
        if (
            transfer.sender_wallet_id not in wallet_ids
            and transfer.receiver_wallet_id not in wallet_ids
        ):
            raise HTTPException(status_code=404, detail="Transfer not found.")

    return transfer


@router.post("/{transfer_id}/cancel", response_model=TransferResponse)
def cancel_transfer(
    transfer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # The current service completes transfers synchronously.
    # A completed transfer must be reversed, not cancelled.
    raise HTTPException(
        status_code=409,
        detail=(
            "Cancellation is not available for synchronous transfers. "
            "Completed transfers require a separate reversal operation."
        ),
    )
