import secrets
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    LedgerEntry,
    TransactionLimit,
    User,
    Wallet,
    Withdrawal,
)
from app.repositories import withdrawal_repository
from app.schemas.withdrawal import WithdrawalCreateRequest
from app.services.audit_log_service import create_audit_log
from app.services.notification_service import create_notification


PRIVILEGED_ROLES = {"SUPER_ADMIN", "ADMIN", "SUPPORT_AGENT"}


def _has_privileged_role(current_user: User) -> bool:
    return bool(
        {role.name for role in current_user.roles}
        & PRIVILEGED_ROLES
    )


def _get_user_wallets(
    db: Session,
    user_id: int,
) -> list[Wallet]:
    statement = select(Wallet).where(Wallet.user_id == user_id)
    return list(db.scalars(statement).all())


def _get_utc_day_bounds() -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    start = datetime.combine(
        now.date(),
        time.min,
        tzinfo=timezone.utc,
    )
    end = start + timedelta(days=1)
    return start, end


def create_withdrawal(
    db: Session,
    current_user: User,
    wallet_id: int,
    data: WithdrawalCreateRequest,
) -> Withdrawal:
    amount = data.amount

    if not amount.is_finite() or amount <= Decimal("0"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Withdrawal amount must be a positive, finite value.",
        )

    if amount.as_tuple().exponent < -2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Withdrawal amount cannot have more than "
                "two decimal places."
            ),
        )

    try:
        wallet = db.scalar(
            select(Wallet)
            .where(Wallet.id == wallet_id)
            .with_for_update()
        )

        if wallet is None or wallet.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Wallet not found.",
            )

        if wallet.status != "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Withdrawals are not allowed for this wallet.",
            )

        limits = db.get(TransactionLimit, 1)

        if limits is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Transaction limits are not configured.",
            )

        if amount > limits.max_transaction_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Withdrawal exceeds the maximum transaction "
                    f"amount of {limits.max_transaction_amount}."
                ),
            )

        day_start, day_end = _get_utc_day_bounds()

        daily_total = (
            withdrawal_repository.sum_completed_for_wallet_since(
                db,
                wallet.id,
                day_start,
                day_end,
            )
        )

        daily_count = (
            withdrawal_repository.count_completed_for_wallet_since(
                db,
                wallet.id,
                day_start,
                day_end,
            )
        )

        if daily_total + amount > limits.daily_withdrawal_limit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Daily withdrawal limit exceeded.",
            )

        if daily_count >= limits.max_transactions_per_day:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Daily transaction count limit exceeded.",
            )

        if wallet.available_balance < amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient wallet balance.",
            )

        balance_before = wallet.available_balance
        balance_after = balance_before - amount

        wallet.available_balance = balance_after

        withdrawal = Withdrawal(
            wallet_id=wallet.id,
            amount=amount,
            currency=wallet.currency,
            status="COMPLETED",
            reference_number=f"WDR-{secrets.token_hex(12).upper()}",
            completed_at=datetime.now(timezone.utc),
        )

        withdrawal_repository.add(db, withdrawal)
        db.flush()

        db.add(
            LedgerEntry(
                wallet_id=wallet.id,
                transaction_type="WITHDRAWAL",
                amount=-amount,
                balance_before=balance_before,
                balance_after=balance_after,
                reference_entity="WITHDRAWAL",
                reference_id=withdrawal.id,
                description="Wallet withdrawal",
                created_by=current_user.id,
            )
        )

        create_audit_log(
            db,
            user_id=current_user.id,
            action="WITHDRAWAL_COMPLETED",
            entity_type="WITHDRAWAL",
            entity_id=withdrawal.id,
            metadata={
                "amount": str(amount),
                "currency": wallet.currency,
                "wallet_id": wallet.id,
                "status": withdrawal.status,
            },
        )

        create_notification(
            db,
            user_id=wallet.user_id,
            event_type="WITHDRAWAL_COMPLETED",
            title="Withdrawal completed",
            message=(
                f"Your withdrawal of {amount} {wallet.currency} "
                "completed successfully."
            ),
            entity_type="WITHDRAWAL",
            entity_id=withdrawal.id,
        )

        # Financial changes and related records commit together.
        db.commit()
        db.refresh(withdrawal)
        return withdrawal

    except Exception:
        db.rollback()
        raise


def list_withdrawals(
    db: Session,
    current_user: User,
) -> list[Withdrawal]:
    if _has_privileged_role(current_user):
        return withdrawal_repository.list_all(db)

    wallets = _get_user_wallets(db, current_user.id)
    wallet_ids = [wallet.id for wallet in wallets]

    return withdrawal_repository.list_for_wallets(
        db,
        wallet_ids,
    )


def get_withdrawal(
    db: Session,
    current_user: User,
    withdrawal_id: int,
) -> Withdrawal:
    withdrawal = withdrawal_repository.get_by_id(
        db,
        withdrawal_id,
    )

    if withdrawal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Withdrawal not found.",
        )

    wallet = db.get(Wallet, withdrawal.wallet_id)

    if wallet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated wallet not found.",
        )

    if (
        not _has_privileged_role(current_user)
        and wallet.user_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Withdrawal not found.",
        )

    return withdrawal


def cancel_withdrawal(
    db: Session,
    current_user: User,
    withdrawal_id: int,
) -> Withdrawal:
    try:
        withdrawal = withdrawal_repository.get_by_id(
            db,
            withdrawal_id,
            for_update=True,
        )

        if withdrawal is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Withdrawal not found.",
            )

        wallet = db.scalar(
            select(Wallet)
            .where(Wallet.id == withdrawal.wallet_id)
            .with_for_update()
        )

        if wallet is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated wallet not found.",
            )

        if (
            not _has_privileged_role(current_user)
            and wallet.user_id != current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Withdrawal not found.",
            )

        if withdrawal.status != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only pending withdrawals can be cancelled.",
            )

        withdrawal.status = "CANCELLED"

        create_audit_log(
            db,
            user_id=current_user.id,
            action="WITHDRAWAL_CANCELLED",
            entity_type="WITHDRAWAL",
            entity_id=withdrawal.id,
            metadata={
                "wallet_id": wallet.id,
                "status": withdrawal.status,
            },
        )

        create_notification(
            db,
            user_id=wallet.user_id,
            event_type="WITHDRAWAL_CANCELLED",
            title="Withdrawal cancelled",
            message=(
                f"Your pending withdrawal {withdrawal.id} "
                "was cancelled."
            ),
            entity_type="WITHDRAWAL",
            entity_id=withdrawal.id,
        )

        db.commit()
        db.refresh(withdrawal)
        return withdrawal

    except Exception:
        db.rollback()
        raise