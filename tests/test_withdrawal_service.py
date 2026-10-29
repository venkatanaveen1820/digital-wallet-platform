
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import event, select

from app.models import LedgerEntry, TransactionLimit, Wallet, Withdrawal
from app.schemas.withdrawal import WithdrawalCreateRequest
from app.services import withdrawal_service

from test_transfer_service import create_test_users_and_wallets


def ensure_transaction_limits(db_session):
    limits = db_session.get(TransactionLimit, 1)

    if limits is None:
        limits = TransactionLimit(
            id=1,
            max_transaction_amount=Decimal("50000.00"),
            daily_transfer_limit=Decimal("100000.00"),
            daily_withdrawal_limit=Decimal("25000.00"),
            max_transactions_per_day=20,
            suspicious_amount_threshold=Decimal("25000.00"),
            rapid_transfer_count=5,
            rapid_transfer_window_minutes=10,
        )
        db_session.add(limits)
        db_session.flush()

    return limits


def test_successful_withdrawal_creates_ledger_entry(db_session):
    user, _, wallet, _ = create_test_users_and_wallets(db_session)
    ensure_transaction_limits(db_session)

    original_balance = wallet.available_balance

    withdrawal = withdrawal_service.create_withdrawal(
        db_session,
        user,
        wallet.id,
        WithdrawalCreateRequest(amount=Decimal("100.00")),
    )

    db_session.refresh(wallet)

    assert withdrawal.status == "COMPLETED"
    assert withdrawal.amount == Decimal("100.00")
    assert withdrawal.wallet_id == wallet.id
    assert wallet.available_balance == original_balance - Decimal("100.00")

    entries = db_session.scalars(
        select(LedgerEntry).where(
            LedgerEntry.reference_entity == "WITHDRAWAL",
            LedgerEntry.reference_id == withdrawal.id,
        )
    ).all()

    assert len(entries) == 1

    entry = entries[0]
    assert entry.wallet_id == wallet.id
    assert entry.transaction_type == "WITHDRAWAL"
    assert entry.amount == Decimal("-100.00")
    assert entry.balance_before == original_balance
    assert entry.balance_after == original_balance - Decimal("100.00")
    assert entry.created_by == user.id


def test_withdrawal_from_another_users_wallet_is_rejected(db_session):
    _, other_user, wallet, _ = create_test_users_and_wallets(db_session)
    ensure_transaction_limits(db_session)

    with pytest.raises(HTTPException) as exc_info:
        withdrawal_service.create_withdrawal(
            db_session,
            other_user,
            wallet.id,
            WithdrawalCreateRequest(amount=Decimal("50.00")),
        )

    assert exc_info.value.status_code == 404



def test_withdrawal_with_insufficient_balance_is_rejected(db_session):
    user, _, wallet, _ = create_test_users_and_wallets(db_session)
    ensure_transaction_limits(db_session)

    wallet_id = wallet.id
    original_balance = wallet.available_balance
    amount = original_balance + Decimal("1.00")

    with pytest.raises(HTTPException) as exc_info:
        withdrawal_service.create_withdrawal(
            db_session,
            user,
            wallet_id,
            WithdrawalCreateRequest(amount=amount),
        )

    assert exc_info.value.status_code == 400

    # The service rollback may undo the test fixture's uncommitted setup.
    # Check the current session without assuming the wallet still exists.
    refreshed_wallet = db_session.get(Wallet, wallet_id)

    if refreshed_wallet is not None:
        assert refreshed_wallet.available_balance == original_balance

    withdrawals = db_session.scalars(
        select(Withdrawal).where(Withdrawal.wallet_id == wallet_id)
    ).all()

    assert withdrawals == []



def test_daily_withdrawal_limit_is_enforced(db_session):
    user, _, wallet, _ = create_test_users_and_wallets(db_session)
    limits = ensure_transaction_limits(db_session)

    limits.daily_withdrawal_limit = Decimal("150.00")
    db_session.flush()

    withdrawal_service.create_withdrawal(
        db_session,
        user,
        wallet.id,
        WithdrawalCreateRequest(amount=Decimal("100.00")),
    )

    with pytest.raises(HTTPException) as exc_info:
        withdrawal_service.create_withdrawal(
            db_session,
            user,
            wallet.id,
            WithdrawalCreateRequest(amount=Decimal("100.00")),
        )

    assert exc_info.value.status_code == 400
    assert "daily withdrawal limit" in exc_info.value.detail.lower()


def test_ledger_failure_rolls_back_withdrawal(db_session):
    user, _, wallet, _ = create_test_users_and_wallets(db_session)
    ensure_transaction_limits(db_session)

    wallet_id = wallet.id
    original_balance = wallet.available_balance

    def fail_withdrawal_ledger_flush(session, flush_context, instances):
        if any(
            isinstance(obj, LedgerEntry)
            and obj.reference_entity == "WITHDRAWAL"
            for obj in session.new
        ):
            raise RuntimeError("Simulated withdrawal ledger failure")

    event.listen(db_session, "before_flush", fail_withdrawal_ledger_flush)

    try:
        with pytest.raises(
            RuntimeError,
            match="Simulated withdrawal ledger failure",
        ):
            withdrawal_service.create_withdrawal(
                db_session,
                user,
                wallet_id,
                WithdrawalCreateRequest(amount=Decimal("100.00")),
            )
    finally:
        event.remove(db_session, "before_flush", fail_withdrawal_ledger_flush)

    # Reload persisted state after the service rollback.
    refreshed_wallet = db_session.get(Wallet, wallet_id)

    if refreshed_wallet is not None:
        assert refreshed_wallet.available_balance == original_balance

    remaining_withdrawals = db_session.scalars(
        select(Withdrawal).where(Withdrawal.wallet_id == wallet_id)
    ).all()

    assert remaining_withdrawals == []



def test_withdrawal_from_frozen_wallet_is_rejected(db_session):
    user, _, wallet, _ = create_test_users_and_wallets(db_session)
    ensure_transaction_limits(db_session)

    wallet.status = "FROZEN"
    db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        withdrawal_service.create_withdrawal(
            db_session,
            user,
            wallet.id,
            WithdrawalCreateRequest(amount=Decimal("50.00")),
        )

    assert exc_info.value.status_code == 409
    assert "not allowed" in exc_info.value.detail.lower()


def test_withdrawal_above_maximum_transaction_amount_is_rejected(db_session):
    user, _, wallet, _ = create_test_users_and_wallets(db_session)
    limits = ensure_transaction_limits(db_session)

    limits.max_transaction_amount = Decimal("100.00")
    db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        withdrawal_service.create_withdrawal(
            db_session,
            user,
            wallet.id,
            WithdrawalCreateRequest(amount=Decimal("101.00")),
        )

    assert exc_info.value.status_code == 400
    assert "maximum transaction amount" in exc_info.value.detail.lower()


def test_daily_transaction_count_limit_is_enforced(db_session):
    user, _, wallet, _ = create_test_users_and_wallets(db_session)
    limits = ensure_transaction_limits(db_session)

    limits.max_transaction_amount = Decimal("50000.00")
    limits.daily_withdrawal_limit = Decimal("50000.00")
    limits.max_transactions_per_day = 1
    db_session.flush()

    withdrawal_service.create_withdrawal(
        db_session,
        user,
        wallet.id,
        WithdrawalCreateRequest(amount=Decimal("50.00")),
    )

    with pytest.raises(HTTPException) as exc_info:
        withdrawal_service.create_withdrawal(
            db_session,
            user,
            wallet.id,
            WithdrawalCreateRequest(amount=Decimal("50.00")),
        )

    assert exc_info.value.status_code == 400
    assert "transaction count limit" in exc_info.value.detail.lower()


def test_completed_withdrawal_cannot_be_cancelled(db_session):
    user, _, wallet, _ = create_test_users_and_wallets(db_session)
    ensure_transaction_limits(db_session)

    withdrawal = withdrawal_service.create_withdrawal(
        db_session,
        user,
        wallet.id,
        WithdrawalCreateRequest(amount=Decimal("50.00")),
    )

    assert withdrawal.status == "COMPLETED"

    with pytest.raises(HTTPException) as exc_info:
        withdrawal_service.cancel_withdrawal(
            db_session,
            user,
            withdrawal.id,
        )

    assert exc_info.value.status_code == 409
    assert "only pending withdrawals" in exc_info.value.detail.lower()

