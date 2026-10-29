from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import LedgerEntry, Role, Transfer
from app.schemas.refund import RefundCreateRequest, RefundRejectRequest
from app.services import refund_service
from test_transfer_service import create_test_users_and_wallets


def create_completed_transfer(db_session):
    """Create users, wallets, and a completed transfer for testing."""
    sender, receiver, sender_wallet, receiver_wallet = (
        create_test_users_and_wallets(db_session)
    )

    amount = Decimal("100.00")

    # Simulate the balances after the original transfer has settled.
    sender_wallet.available_balance -= amount
    receiver_wallet.available_balance += amount

    transfer = Transfer(
        sender_wallet_id=sender_wallet.id,
        receiver_wallet_id=receiver_wallet.id,
        amount=amount,
        currency=sender_wallet.currency,
        status="COMPLETED",
        reference=(
            f"TRF-REFUND-TEST-{sender_wallet.id}-{receiver_wallet.id}"
        ),
    )

    db_session.add(transfer)
    db_session.flush()

    return (
        sender,
        receiver,
        sender_wallet,
        receiver_wallet,
        transfer,
    )


def grant_admin_role(db_session, user):
    """Give a test user the ADMIN role."""
    role = db_session.scalar(
        select(Role).where(Role.name == "ADMIN")
    )

    if role is None:
        pytest.skip(
            "Seed the standard roles before running refund approval tests."
        )

    if role not in user.roles:
        user.roles.append(role)
        db_session.flush()


def request_refund(db_session, sender, transfer, amount):
    """Submit a refund request using a decimal amount."""
    request = RefundCreateRequest(
        transfer_id=transfer.id,
        amount=Decimal(amount),
    )

    return refund_service.create_refund(
        db_session,
        sender,
        request,
    )


def test_create_partial_refund_request(db_session):
    sender, _, _, _, transfer = create_completed_transfer(db_session)

    refund = request_refund(
        db_session, sender, transfer, "35.00"
    )

    assert refund.status == "REQUESTED"
    assert refund.amount == Decimal("35.00")
    assert refund.transfer_id == transfer.id


def test_create_full_refund_request(db_session):
    sender, _, _, _, transfer = create_completed_transfer(db_session)

    refund = request_refund(
        db_session, sender, transfer, "100.00"
    )

    assert refund.amount == transfer.amount
    assert refund.status == "REQUESTED"


def test_multiple_partial_refunds_up_to_original_amount(db_session):
    sender, _, _, _, transfer = create_completed_transfer(db_session)

    first = request_refund(
        db_session, sender, transfer, "35.00"
    )
    second = request_refund(
        db_session, sender, transfer, "65.00"
    )

    assert first.amount + second.amount == transfer.amount


def test_refund_request_cannot_exceed_remaining_amount(db_session):
    sender, _, _, _, transfer = create_completed_transfer(db_session)

    request_refund(db_session, sender, transfer, "70.00")

    with pytest.raises(HTTPException) as exc_info:
        request_refund(db_session, sender, transfer, "30.01")

    assert exc_info.value.status_code == 409


def test_rejected_refund_releases_reserved_amount(db_session):
    sender, reviewer, _, _, transfer = create_completed_transfer(
        db_session
    )
    grant_admin_role(db_session, reviewer)

    first = request_refund(
        db_session, sender, transfer, "70.00"
    )

    refund_service.reject_refund(
        db_session,
        reviewer,
        first.id,
        RefundRejectRequest(
            reason="Supporting evidence is insufficient"
        ),
    )

    # Since the first request was rejected, its reserved amount is released.
    second = request_refund(
        db_session, sender, transfer, "100.00"
    )

    assert second.amount == Decimal("100.00")


def test_only_original_sender_can_request_refund(db_session):
    _, receiver, _, _, transfer = create_completed_transfer(db_session)

    with pytest.raises(HTTPException) as exc_info:
        request_refund(
            db_session, receiver, transfer, "10.00"
        )

    assert exc_info.value.status_code == 404


def test_non_completed_transfer_cannot_be_refunded(db_session):
    sender, _, _, _, transfer = create_completed_transfer(db_session)

    transfer.status = "FAILED"
    db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        request_refund(
            db_session, sender, transfer, "10.00"
        )

    assert exc_info.value.status_code == 409


def test_closed_wallet_prevents_refund_request(db_session):
    sender, _, _, receiver_wallet, transfer = (
        create_completed_transfer(db_session)
    )

    receiver_wallet.status = "CLOSED"
    db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        request_refund(
            db_session, sender, transfer, "10.00"
        )

    assert exc_info.value.status_code == 409


def test_approval_settles_partial_refund_and_creates_two_ledger_entries(
    db_session,
):
    (
        sender,
        reviewer,
        sender_wallet,
        receiver_wallet,
        transfer,
    ) = create_completed_transfer(db_session)

    grant_admin_role(db_session, reviewer)

    sender_before = sender_wallet.available_balance
    receiver_before = receiver_wallet.available_balance

    refund = request_refund(
        db_session, sender, transfer, "25.00"
    )

    completed = refund_service.approve_refund(
        db_session, reviewer, refund.id
    )

    db_session.refresh(sender_wallet)
    db_session.refresh(receiver_wallet)

    assert completed.status == "COMPLETED"

    # The sender is credited and the original receiver is debited.
    assert (
        sender_wallet.available_balance
        == sender_before + Decimal("25.00")
    )
    assert (
        receiver_wallet.available_balance
        == receiver_before - Decimal("25.00")
    )

    entries = db_session.scalars(
        select(LedgerEntry).where(
            LedgerEntry.reference_entity == "REFUND",
            LedgerEntry.reference_id == refund.id,
        )
    ).all()

    assert len(entries) == 2
    assert (
        sum(
            (entry.amount for entry in entries),
            Decimal("0.00"),
        )
        == Decimal("0.00")
    )
    assert {
        entry.transaction_type for entry in entries
    } == {"REFUND", "REVERSAL"}


def test_completed_refund_cannot_be_approved_twice(db_session):
    sender, reviewer, _, _, transfer = create_completed_transfer(
        db_session
    )
    grant_admin_role(db_session, reviewer)

    refund = request_refund(
        db_session, sender, transfer, "100.00"
    )

    refund_service.approve_refund(
        db_session, reviewer, refund.id
    )

    with pytest.raises(HTTPException) as exc_info:
        refund_service.approve_refund(
            db_session, reviewer, refund.id
        )

    assert exc_info.value.status_code == 409


def test_reject_refund_records_reason_without_changing_balances(
    db_session,
):
    (
        sender,
        reviewer,
        sender_wallet,
        receiver_wallet,
        transfer,
    ) = create_completed_transfer(db_session)

    grant_admin_role(db_session, reviewer)

    sender_before = sender_wallet.available_balance
    receiver_before = receiver_wallet.available_balance

    refund = request_refund(
        db_session, sender, transfer, "40.00"
    )

    rejected = refund_service.reject_refund(
        db_session,
        reviewer,
        refund.id,
        RefundRejectRequest(
            reason="Insufficient supporting information"
        ),
    )

    db_session.refresh(sender_wallet)
    db_session.refresh(receiver_wallet)

    assert rejected.status == "REJECTED"
    assert (
        rejected.rejection_reason
        == "Insufficient supporting information"
    )
    assert sender_wallet.available_balance == sender_before
    assert receiver_wallet.available_balance == receiver_before

    entries = db_session.scalars(
        select(LedgerEntry).where(
            LedgerEntry.reference_entity == "REFUND",
            LedgerEntry.reference_id == refund.id,
        )
    ).all()

    assert entries == []


def test_customer_cannot_approve_refund(db_session):
    sender, _, _, _, transfer = create_completed_transfer(db_session)

    refund = request_refund(
        db_session, sender, transfer, "20.00"
    )

    with pytest.raises(HTTPException) as exc_info:
        refund_service.approve_refund(
            db_session, sender, refund.id
        )

    assert exc_info.value.status_code == 403