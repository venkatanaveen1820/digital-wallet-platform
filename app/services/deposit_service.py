import secrets
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Deposit, LedgerEntry, User, Wallet
from app.repositories import deposit_repository
from app.schemas.deposit import DepositCreateRequest
from app.services.audit_log_service import create_audit_log
from app.services.notification_service import create_notification


PRIVILEGED_ROLES = {"SUPER_ADMIN", "ADMIN", "SUPPORT_AGENT"}

MAX_WALLET_BALANCE = Decimal("9999999999999999.99")


def create_deposit(
    db: Session,
    current_user: User,
    wallet_id: int,
    data: DepositCreateRequest,
) -> Deposit:
    amount = data.amount

    if not amount.is_finite() or amount <= 0:
        raise HTTPException(
            status_code=422,
            detail="Amount must be a positive finite value.",
        )

    if amount.as_tuple().exponent < -2:
        raise HTTPException(
            status_code=422,
            detail="Amount cannot have more than two decimal places.",
        )

    try:
        wallet = db.scalar(
            select(Wallet)
            .where(Wallet.id == wallet_id)
            .with_for_update()
        )

        if wallet is None or wallet.user_id != current_user.id:
            raise HTTPException(
                status_code=404,
                detail="Wallet not found.",
            )

        if wallet.status != "ACTIVE":
            raise HTTPException(
                status_code=409,
                detail="Deposits are allowed only for active wallets.",
            )

        if amount.adjusted() > 15:
            raise HTTPException(
                status_code=422,
                detail="Amount exceeds the supported wallet limit.",
            )

        balance_before = wallet.available_balance
        balance_after = balance_before + amount

        if balance_after > MAX_WALLET_BALANCE:
            raise HTTPException(
                status_code=409,
                detail="Deposit would exceed the supported wallet balance.",
            )

        now = datetime.now(timezone.utc)
        reference_number = f"DEP-{secrets.token_hex(16).upper()}"

        deposit = Deposit(
            wallet_id=wallet.id,
            amount=amount,
            currency=wallet.currency,
            status="COMPLETED",
            reference_number=reference_number,
            completed_at=now,
        )

        wallet.available_balance = balance_after
        deposit_repository.add(db, deposit)

        # Obtain the deposit ID for the ledger and related records.
        db.flush()

        ledger_entry = LedgerEntry(
            wallet_id=wallet.id,
            transaction_type="DEPOSIT",
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            reference_entity="DEPOSIT",
            reference_id=deposit.id,
            description=f"Wallet deposit {reference_number}",
            created_by=current_user.id,
            metadata_json={
                "deposit_reference": reference_number,
                "currency": wallet.currency,
            },
        )

        db.add(ledger_entry)
        db.flush()

        create_audit_log(
            db,
            user_id=current_user.id,
            action="DEPOSIT_COMPLETED",
            entity_type="DEPOSIT",
            entity_id=deposit.id,
            metadata={
                "amount": str(amount),
                "currency": wallet.currency,
                "wallet_id": wallet.id,
                "status": deposit.status,
            },
        )

        create_notification(
            db,
            user_id=wallet.user_id,
            event_type="DEPOSIT_COMPLETED",
            title="Deposit completed",
            message=(
                f"Your deposit of {amount} {wallet.currency} "
                "completed successfully."
            ),
            entity_type="DEPOSIT",
            entity_id=deposit.id,
        )

        # Deposit, balance, ledger, audit and notification commit together.
        db.commit()
        db.refresh(deposit)

        return deposit

    except Exception:
        db.rollback()
        raise


def list_deposits(
    db: Session,
    current_user: User,
) -> list[Deposit]:
    is_privileged = any(
        role.name in PRIVILEGED_ROLES
        for role in current_user.roles
    )

    if is_privileged:
        return list(
            db.scalars(
                select(Deposit).order_by(
                    Deposit.created_at.desc(),
                    Deposit.id.desc(),
                )
            ).all()
        )

    wallet_ids = list(
        db.scalars(
            select(Wallet.id).where(
                Wallet.user_id == current_user.id
            )
        ).all()
    )

    return deposit_repository.list_for_wallets(db, wallet_ids)


def get_deposit(
    db: Session,
    current_user: User,
    deposit_id: int,
) -> Deposit:
    deposit = db.scalar(
        select(Deposit)
        .join(Wallet, Deposit.wallet_id == Wallet.id)
        .where(Deposit.id == deposit_id)
    )

    if deposit is None:
        raise HTTPException(
            status_code=404,
            detail="Deposit not found.",
        )

    is_privileged = any(
        role.name in PRIVILEGED_ROLES
        for role in current_user.roles
    )

    if not is_privileged:
        wallet = db.get(Wallet, deposit.wallet_id)

        if wallet is None or wallet.user_id != current_user.id:
            raise HTTPException(
                status_code=404,
                detail="Deposit not found.",
            )

    return deposit