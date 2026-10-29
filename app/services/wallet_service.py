from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User, Wallet
from app.repositories import wallet_repository
from app.schemas.wallet import WalletCreateRequest
from app.services.audit_log_service import create_audit_log
from app.services.notification_service import create_notification


ALLOWED_TRANSITIONS = {
    "ACTIVE": {"FROZEN", "SUSPENDED", "CLOSED"},
    "FROZEN": {"ACTIVE", "SUSPENDED", "CLOSED"},
    "SUSPENDED": {"ACTIVE", "CLOSED"},
    "CLOSED": set(),
}


def create_wallet(
    db: Session,
    current_user: User,
    data: WalletCreateRequest,
) -> Wallet:
    wallet = Wallet(
        user_id=current_user.id,
        currency=data.currency,
        available_balance=Decimal("0.00"),
        pending_balance=Decimal("0.00"),
        status="ACTIVE",
    )

    try:
        wallet_repository.add(db, wallet)
        db.flush()

        create_audit_log(
            db,
            user_id=current_user.id,
            action="WALLET_CREATED",
            entity_type="WALLET",
            entity_id=wallet.id,
            metadata={
                "currency": wallet.currency,
                "status": wallet.status,
            },
        )

        create_notification(
            db,
            user_id=current_user.id,
            event_type="WALLET_CREATED",
            title="Wallet created",
            message=(
                f"Your {wallet.currency} wallet was created successfully."
            ),
            entity_type="WALLET",
            entity_id=wallet.id,
        )

        db.commit()
        db.refresh(wallet)
        return wallet

    except Exception:
        db.rollback()
        raise


def list_my_wallets(
    db: Session,
    current_user: User,
) -> list[Wallet]:
    return wallet_repository.list_owned_wallets(
        db,
        current_user.id,
    )


def get_my_wallet(
    db: Session,
    current_user: User,
    wallet_id: int,
) -> Wallet:
    wallet = wallet_repository.get_owned_wallet(
        db,
        wallet_id,
        current_user.id,
    )

    if wallet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found.",
        )

    return wallet


def update_wallet_status(
    db: Session,
    current_user: User,
    wallet_id: int,
    new_status: str,
) -> Wallet:
    try:
        wallet = db.scalar(
            select(Wallet)
            .where(Wallet.id == wallet_id)
            .with_for_update()
        )

        if wallet is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Wallet not found.",
            )

        if new_status == wallet.status:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Wallet is already {wallet.status}.",
            )

        allowed = ALLOWED_TRANSITIONS.get(wallet.status, set())

        if new_status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Invalid wallet status transition: "
                    f"{wallet.status} -> {new_status}."
                ),
            )

        if new_status == "CLOSED":
            if (
                wallet.available_balance != Decimal("0.00")
                or wallet.pending_balance != Decimal("0.00")
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Wallet can be closed only when both "
                        "available and pending balances are zero."
                    ),
                )

        previous_status = wallet.status
        wallet.status = new_status

        if new_status == "FROZEN":
            action = "WALLET_FROZEN"
        elif previous_status == "FROZEN" and new_status == "ACTIVE":
            action = "WALLET_UNFROZEN"
        else:
            action = "WALLET_STATUS_CHANGED"

        create_audit_log(
            db,
            user_id=current_user.id,
            action=action,
            entity_type="WALLET",
            entity_id=wallet.id,
            metadata={
                "old_status": previous_status,
                "new_status": new_status,
            },
        )

        if new_status == "FROZEN":
            create_notification(
                db,
                user_id=wallet.user_id,
                event_type="WALLET_FROZEN",
                title="Wallet frozen",
                message=f"Your wallet {wallet.id} has been frozen.",
                entity_type="WALLET",
                entity_id=wallet.id,
            )

        elif previous_status == "FROZEN" and new_status == "ACTIVE":
            create_notification(
                db,
                user_id=wallet.user_id,
                event_type="WALLET_UNFROZEN",
                title="Wallet reactivated",
                message=f"Your wallet {wallet.id} is active again.",
                entity_type="WALLET",
                entity_id=wallet.id,
            )

        db.commit()
        db.refresh(wallet)
        return wallet

    except Exception:
        db.rollback()
        raise