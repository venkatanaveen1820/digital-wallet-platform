
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TransactionLimit
from app.schemas.transaction_limit import TransactionLimitUpdate


DEFAULT_LIMITS = {
    "id": 1,
    "max_transaction_amount": "50000.00",
    "daily_transfer_limit": "100000.00",
    "daily_withdrawal_limit": "25000.00",
    "max_transactions_per_day": 20,
    "suspicious_amount_threshold": "25000.00",
    "rapid_transfer_count": 5,
    "rapid_transfer_window_minutes": 10,
}


def get_or_create_limits(db: Session) -> TransactionLimit:
    limits = db.get(TransactionLimit, 1)

    if limits is not None:
        return limits

    try:
        limits = TransactionLimit(**DEFAULT_LIMITS)
        db.add(limits)
        db.commit()
        db.refresh(limits)
        return limits
    except Exception:
        db.rollback()

        # Another request may have initialized the singleton row.
        limits = db.get(TransactionLimit, 1)
        if limits is not None:
            return limits
        raise


def get_transaction_limits(db: Session) -> TransactionLimit:
    return get_or_create_limits(db)


def update_transaction_limits(
    db: Session,
    data: TransactionLimitUpdate,
) -> TransactionLimit:
    limits = get_or_create_limits(db)
    updates = data.model_dump(exclude_unset=True)

    # A daily cap must not be lower than the per-transaction cap.
    effective_max = updates.get(
        "max_transaction_amount", limits.max_transaction_amount
    )
    effective_transfer = updates.get(
        "daily_transfer_limit", limits.daily_transfer_limit
    )
    effective_withdrawal = updates.get(
        "daily_withdrawal_limit", limits.daily_withdrawal_limit
    )

    if effective_transfer < effective_max:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_TRANSACTION_LIMIT_CONFIGURATION",
                "message": (
                    "Daily transfer limit cannot be lower than "
                    "the maximum transaction amount."
                ),
            },
        )

    if effective_withdrawal < effective_max:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_TRANSACTION_LIMIT_CONFIGURATION",
                "message": (
                    "Daily withdrawal limit cannot be lower than "
                    "the maximum transaction amount."
                ),
            },
        )

    try:
        for field, value in updates.items():
            setattr(limits, field, value)

        db.commit()
        db.refresh(limits)
        return limits
    except Exception:
        db.rollback()
        raise
