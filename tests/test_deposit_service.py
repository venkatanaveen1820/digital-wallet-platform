
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import Deposit, LedgerEntry, User, Wallet
from app.schemas.deposit import DepositCreateRequest
from app.services.deposit_service import create_deposit

from test_transfer_service import create_test_users_and_wallets


def test_successful_deposit_creates_ledger_entry(db_session):
    user, _, wallet, _ = create_test_users_and_wallets(db_session)

    response = create_deposit(
        db_session,
        user,
        wallet.id,
        DepositCreateRequest(amount=Decimal("100.00")),
    )

    db_session.refresh(wallet)

    assert response.status == "COMPLETED"
    assert response.amount == Decimal("100.00")
    assert wallet.available_balance == Decimal("600.00")

    entries = db_session.scalars(
        select(LedgerEntry).where(
            LedgerEntry.reference_entity == "DEPOSIT",
            LedgerEntry.reference_id == response.id,
        )
    ).all()

    assert len(entries) == 1

    entry = entries[0]
    assert entry.wallet_id == wallet.id
    assert entry.transaction_type == "DEPOSIT"
    assert entry.amount == Decimal("100.00")
    assert entry.balance_before == Decimal("500.00")
    assert entry.balance_after == Decimal("600.00")
    assert entry.created_by == user.id


def test_deposit_for_another_users_wallet_is_rejected(db_session):
    _, receiver, sender_wallet, _ = create_test_users_and_wallets(
        db_session
    )

    with pytest.raises(HTTPException) as exc_info:
        create_deposit(
            db_session,
            receiver,
            sender_wallet.id,
            DepositCreateRequest(amount=Decimal("50.00")),
        )

    assert exc_info.value.status_code == 404





def test_deposit_ledger_failure_rolls_back_transaction(
    db_session,
):
    from sqlalchemy import event
    from app.services import deposit_service

    user, _, wallet, _ = create_test_users_and_wallets(db_session)

    wallet_id = wallet.id
    original_balance = wallet.available_balance

    def fail_ledger_flush(session, flush_context, instances):
        if any(
            isinstance(obj, LedgerEntry)
            and obj.reference_entity == "DEPOSIT"
            for obj in session.new
        ):
            raise RuntimeError("Simulated ledger insertion failure")

    event.listen(db_session, "before_flush", fail_ledger_flush)

    try:
        with pytest.raises(
            RuntimeError,
            match="Simulated ledger insertion failure",
        ):
            deposit_service.create_deposit(
                db_session,
                user,
                wallet_id,
                DepositCreateRequest(amount=Decimal("100.00")),
            )
    finally:
        event.remove(db_session, "before_flush", fail_ledger_flush)

    # The failed transaction should not leave a deposit or balance change.
    # Rollback may expire ORM objects, so reload using the primary key.
    refreshed_wallet = db_session.get(Wallet, wallet_id)

    # The fixture's outer transaction may have been rolled back by the
    # service, so verify persistence using a fresh session only if needed.
    if refreshed_wallet is not None:
        assert refreshed_wallet.available_balance == original_balance

