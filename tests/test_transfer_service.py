
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import LedgerEntry, User, Wallet, Transfer
from app.schemas.transfer import TransferCreateRequest
from app.services.transfer_service import create_transfer
from app.models.idempotency_key import IdempotencyKey

def create_test_users_and_wallets(db_session):
    """Create two independent users and funded wallets for a test."""
    suffix = uuid4().hex

    sender_user = User(
        email=f"sender-{suffix}@example.test",
        full_name="Test Sender",
        password_hash="not-a-real-password-hash",
        is_active=True,
    )
    receiver_user = User(
        email=f"receiver-{suffix}@example.test",
        full_name="Test Receiver",
        password_hash="not-a-real-password-hash",
        is_active=True,
    )

    db_session.add_all([sender_user, receiver_user])
    db_session.flush()

    sender_wallet = Wallet(
        user_id=sender_user.id,
        currency="INR",
        available_balance=Decimal("500.00"),
        pending_balance=Decimal("0.00"),
        status="ACTIVE",
    )
    receiver_wallet = Wallet(
        user_id=receiver_user.id,
        currency="INR",
        available_balance=Decimal("200.00"),
        pending_balance=Decimal("0.00"),
        status="ACTIVE",
    )

    db_session.add_all([sender_wallet, receiver_wallet])
    db_session.flush()

    return sender_user, receiver_user, sender_wallet, receiver_wallet


def test_successful_transfer_creates_balanced_ledger_entries(db_session):
    sender, _, sender_wallet, receiver_wallet = (
        create_test_users_and_wallets(db_session)
    )

    response = create_transfer(
        db_session,
        sender,
        TransferCreateRequest(
            sender_wallet_id=sender_wallet.id,
            receiver_wallet_id=receiver_wallet.id,
            amount=Decimal("100.00"),
        ),
        idempotency_key=f"test-success-{uuid4().hex}",
    )

    assert response["status"] == "COMPLETED"
    assert Decimal(response["amount"]) == Decimal("100.00")

    db_session.refresh(sender_wallet)
    db_session.refresh(receiver_wallet)

    assert sender_wallet.available_balance == Decimal("400.00")
    assert receiver_wallet.available_balance == Decimal("300.00")

    entries = list(
        db_session.scalars(
            select(LedgerEntry).where(
                LedgerEntry.reference_entity == "TRANSFER",
                LedgerEntry.reference_id == response["id"],
            )
        ).all()
    )

    assert len(entries) == 2

    debit = next(e for e in entries if e.transaction_type == "TRANSFER_DEBIT")
    credit = next(e for e in entries if e.transaction_type == "TRANSFER_CREDIT")

    assert debit.amount == Decimal("-100.00")
    assert debit.balance_before == Decimal("500.00")
    assert debit.balance_after == Decimal("400.00")

    assert credit.amount == Decimal("100.00")
    assert credit.balance_before == Decimal("200.00")
    assert credit.balance_after == Decimal("300.00")


def test_insufficient_balance_is_rejected(db_session):
    sender, _, sender_wallet, receiver_wallet = (
        create_test_users_and_wallets(db_session)
    )

    with pytest.raises(HTTPException) as exc_info:
        create_transfer(
            db_session,
            sender,
            TransferCreateRequest(
                sender_wallet_id=sender_wallet.id,
                receiver_wallet_id=receiver_wallet.id,
                amount=Decimal("999.00"),
            ),
            idempotency_key=f"test-insufficient-{uuid4().hex}",
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Insufficient available balance."


def test_user_cannot_transfer_from_another_users_wallet(db_session):
    sender, receiver, sender_wallet, receiver_wallet = (
        create_test_users_and_wallets(db_session)
    )

    # The receiver is not the owner of the sender wallet.
    with pytest.raises(HTTPException) as exc_info:
        create_transfer(
            db_session,
            receiver,
            TransferCreateRequest(
                sender_wallet_id=sender_wallet.id,
                receiver_wallet_id=receiver_wallet.id,
                amount=Decimal("10.00"),
            ),
            idempotency_key=f"test-ownership-{uuid4().hex}",
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Sender wallet not found."

def test_idempotent_retry_returns_original_transfer(db_session):
    sender, _, sender_wallet, receiver_wallet = (
        create_test_users_and_wallets(db_session)
    )

    idempotency_key = f"test-retry-{uuid4().hex}"

    request_data = TransferCreateRequest(
        sender_wallet_id=sender_wallet.id,
        receiver_wallet_id=receiver_wallet.id,
        amount=Decimal("100.00"),
    )

    first_response = create_transfer(
        db_session,
        sender,
        request_data,
        idempotency_key=idempotency_key,
    )

    second_response = create_transfer(
        db_session,
        sender,
        request_data,
        idempotency_key=idempotency_key,
    )

    # Both requests must refer to the same transfer.
    assert first_response["id"] == second_response["id"]
    assert first_response["reference"] == second_response["reference"]

    # The transfer must exist only once.
    transfers = db_session.scalars(
        select(Transfer).where(
            Transfer.sender_wallet_id == sender_wallet.id,
            Transfer.receiver_wallet_id == receiver_wallet.id,
        )
    ).all()

    assert len(transfers) == 1

    # Exactly two ledger entries: one debit and one credit.
    ledger_entries = db_session.scalars(
        select(LedgerEntry).where(
            LedgerEntry.reference_entity == "TRANSFER",
            LedgerEntry.reference_id == first_response["id"],
        )
    ).all()

    assert len(ledger_entries) == 2

    db_session.refresh(sender_wallet)
    db_session.refresh(receiver_wallet)

    # The retry must not move the money a second time.
    assert sender_wallet.available_balance == Decimal("400.00")
    assert receiver_wallet.available_balance == Decimal("300.00")


def test_idempotency_key_reuse_with_different_amount_is_rejected(db_session):
    sender, _, sender_wallet, receiver_wallet = (
        create_test_users_and_wallets(db_session)
    )

    idempotency_key = f"test-conflict-{uuid4().hex}"

    first_request = TransferCreateRequest(
        sender_wallet_id=sender_wallet.id,
        receiver_wallet_id=receiver_wallet.id,
        amount=Decimal("100.00"),
    )

    create_transfer(
        db_session,
        sender,
        first_request,
        idempotency_key=idempotency_key,
    )

    different_request = TransferCreateRequest(
        sender_wallet_id=sender_wallet.id,
        receiver_wallet_id=receiver_wallet.id,
        amount=Decimal("150.00"),
    )

    with pytest.raises(HTTPException) as exc_info:
        create_transfer(
            db_session,
            sender,
            different_request,
            idempotency_key=idempotency_key,
        )

    assert exc_info.value.status_code == 409


def test_idempotent_retry_does_not_create_extra_ledger_entries(db_session):
    sender, _, sender_wallet, receiver_wallet = (
        create_test_users_and_wallets(db_session)
    )

    idempotency_key = f"test-ledger-retry-{uuid4().hex}"

    request_data = TransferCreateRequest(
        sender_wallet_id=sender_wallet.id,
        receiver_wallet_id=receiver_wallet.id,
        amount=Decimal("75.00"),
    )

    first_response = create_transfer(
        db_session,
        sender,
        request_data,
        idempotency_key=idempotency_key,
    )

    create_transfer(
        db_session,
        sender,
        request_data,
        idempotency_key=idempotency_key,
    )

    ledger_entries = db_session.scalars(
        select(LedgerEntry).where(
            LedgerEntry.reference_entity == "TRANSFER",
            LedgerEntry.reference_id == first_response["id"],
        )
    ).all()

    assert len(ledger_entries) == 2

    db_session.refresh(sender_wallet)
    db_session.refresh(receiver_wallet)

    assert sender_wallet.available_balance == Decimal("425.00")
    assert receiver_wallet.available_balance == Decimal("275.00")
