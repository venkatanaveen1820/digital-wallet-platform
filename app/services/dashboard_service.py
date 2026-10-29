from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    Deposit,
    Refund,
    Transfer,
    User,
    Wallet,
    Withdrawal,
)

BUSINESS_TIMEZONE = ZoneInfo("Asia/Kolkata")
PENDING_STATUSES = ("PENDING", "PROCESSING")
FAILED_STATUS = "FAILED"


def _today_range() -> tuple[datetime, datetime]:
    now = datetime.now(BUSINESS_TIMEZONE)
    start = datetime.combine(now.date(), time.min, tzinfo=BUSINESS_TIMEZONE)
    return start, start + timedelta(days=1)


def _count(db: Session, model, *conditions) -> int:
    statement = select(func.count()).select_from(model)

    if conditions:
        statement = statement.where(*conditions)

    return int(db.scalar(statement) or 0)


def _currency_totals(
    db: Session,
    model,
    amount_column,
    *conditions,
) -> list[dict]:
    statement = select(
        model.currency,
        func.coalesce(func.sum(amount_column), 0),
    ).group_by(model.currency)

    if conditions:
        statement = statement.where(*conditions)

    rows = db.execute(statement).all()

    return [
        {"currency": currency, "amount": str(amount or Decimal("0.00"))}
        for currency, amount in sorted(rows, key=lambda row: row[0])
    ]


def _merge_currency_totals(
    *groups: list[dict],
) -> list[dict]:
    totals: dict[str, Decimal] = defaultdict(Decimal)

    for group in groups:
        for item in group:
            totals[item["currency"]] += Decimal(item["amount"])

    return [
        {"currency": currency, "amount": str(amount)}
        for currency, amount in sorted(totals.items())
    ]


def _failed_transactions(db: Session) -> int:
    return sum(
        _count(db, model, model.status == FAILED_STATUS)
        for model in (Deposit, Transfer, Withdrawal, Refund)
    )


def _suspicious_transactions(db: Session) -> int:
    return _count(
        db,
        AuditLog,
        AuditLog.action == "SUSPICIOUS_TRANSACTION_DETECTED",
    )


def get_admin_dashboard(db: Session) -> dict:
    start, end = _today_range()

    today_conditions = lambda model: (
        model.created_at >= start,
        model.created_at < end,
    )

    today_count = sum(
        _count(db, model, *today_conditions(model))
        for model in (Deposit, Transfer, Withdrawal)
    )

    # Volume includes completed deposits, transfers, and withdrawals.
    # Refunds are excluded to avoid counting a transfer and its refund
    # as two separate transaction volumes.
    volume_groups = []

    for model in (Deposit, Transfer, Withdrawal):
        volume_groups.append(
            _currency_totals(
                db,
                model,
                model.amount,
                *today_conditions(model),
                model.status == "COMPLETED",
            )
        )

    wallet_balance_groups = [
        _currency_totals(
            db,
            Wallet,
            Wallet.available_balance,
        ),
        _currency_totals(
            db,
            Wallet,
            Wallet.pending_balance,
        ),
    ]

    return {
        "total_users": _count(db, User),
        "active_wallets": _count(db, Wallet, Wallet.status == "ACTIVE"),
        "total_wallet_balance": _merge_currency_totals(
            *wallet_balance_groups
        ),
        "todays_transactions": today_count,
        "todays_transaction_volume": _merge_currency_totals(
            *volume_groups
        ),
        "failed_transactions": _failed_transactions(db),
        "suspicious_transactions": _suspicious_transactions(db),
    }


def get_support_dashboard(db: Session) -> dict:
    return {
        # Refunds awaiting review are counted separately from new requests.
        "pending_reviews": _count(
            db,
            Refund,
            Refund.status == "UNDER_REVIEW",
        ),
        "suspicious_transactions": _suspicious_transactions(db),
        "failed_transactions": _failed_transactions(db),
        "refund_requests": _count(
            db,
            Refund,
            Refund.status == "REQUESTED",
        ),
        "frozen_wallets": _count(
            db,
            Wallet,
            Wallet.status == "FROZEN",
        ),
    }


def _recent_transactions(
    db: Session,
    wallet_ids: list[int],
    limit: int = 10,
) -> list[dict]:
    if not wallet_ids:
        return []

    transactions: list[dict] = []

    queries = [
        (
            Deposit,
            select(Deposit).where(Deposit.wallet_id.in_(wallet_ids)),
            "DEPOSIT",
        ),
        (
            Withdrawal,
            select(Withdrawal).where(
                Withdrawal.wallet_id.in_(wallet_ids)
            ),
            "WITHDRAWAL",
        ),
        (
            Transfer,
            select(Transfer).where(
                or_(
                    Transfer.sender_wallet_id.in_(wallet_ids),
                    Transfer.receiver_wallet_id.in_(wallet_ids),
                )
            ),
            "TRANSFER",
        ),
    ]

    for model, statement, transaction_type in queries:
        rows = db.scalars(
            statement.order_by(model.created_at.desc()).limit(limit)
        ).all()

        for row in rows:
            transactions.append(
                {
                    "transaction_type": transaction_type,
                    "transaction_id": row.id,
                    "amount": str(row.amount),
                    "currency": row.currency,
                    "status": row.status,
                    "created_at": row.created_at,
                }
            )

    transactions.sort(
        key=lambda item: item["created_at"],
        reverse=True,
    )

    return transactions[:limit]


def get_customer_dashboard(db: Session, user: User) -> dict:
    wallets = db.scalars(
        select(Wallet).where(Wallet.user_id == user.id)
    ).all()

    wallet_ids = [wallet.id for wallet in wallets]

    if not wallet_ids:
        return {
            "wallet_balance": [],
            "recent_transactions": [],
            "total_deposits": [],
            "total_transfers": [],
            "total_withdrawals": [],
            "pending_transactions": 0,
        }

    wallet_balance_groups = []

    for column in (Wallet.available_balance, Wallet.pending_balance):
        wallet_balance_groups.append(
            _currency_totals(
                db,
                Wallet,
                column,
                Wallet.user_id == user.id,
            )
        )

    total_deposits = _currency_totals(
        db,
        Deposit,
        Deposit.amount,
        Deposit.wallet_id.in_(wallet_ids),
        Deposit.status == "COMPLETED",
    )

    # Count each transfer once, whether sent or received.
    total_transfers = _currency_totals(
        db,
        Transfer,
        Transfer.amount,
        or_(
            Transfer.sender_wallet_id.in_(wallet_ids),
            Transfer.receiver_wallet_id.in_(wallet_ids),
        ),
        Transfer.status == "COMPLETED",
    )

    total_withdrawals = _currency_totals(
        db,
        Withdrawal,
        Withdrawal.amount,
        Withdrawal.wallet_id.in_(wallet_ids),
        Withdrawal.status == "COMPLETED",
    )

    pending_count = (
        _count(
            db,
            Deposit,
            Deposit.wallet_id.in_(wallet_ids),
            Deposit.status.in_(PENDING_STATUSES),
        )
        + _count(
            db,
            Withdrawal,
            Withdrawal.wallet_id.in_(wallet_ids),
            Withdrawal.status.in_(PENDING_STATUSES),
        )
        + _count(
            db,
            Transfer,
            or_(
                Transfer.sender_wallet_id.in_(wallet_ids),
                Transfer.receiver_wallet_id.in_(wallet_ids),
            ),
            Transfer.status.in_(PENDING_STATUSES),
        )
    )

    return {
        "wallet_balance": _merge_currency_totals(
            *wallet_balance_groups
        ),
        "recent_transactions": _recent_transactions(db, wallet_ids),
        "total_deposits": total_deposits,
        "total_transfers": total_transfers,
        "total_withdrawals": total_withdrawals,
        "pending_transactions": pending_count,
    }