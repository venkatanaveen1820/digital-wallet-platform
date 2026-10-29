
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import sessionmaker

from app.models import (
    AuditLog,
    IdempotencyKey,
    LedgerEntry,
    Notification,
    Transfer,
    User,
    Wallet,
)
from app.schemas.transfer import TransferCreateRequest
from app.services.transfer_service import create_transfer


def test_concurrent_transfers_cannot_overspend(test_engine):
    """Only one of two concurrent transfers may spend the same funds."""
    suffix = uuid4().hex
    amount = Decimal("700.00")
    keys = [f"concurrency-{suffix}-a", f"concurrency-{suffix}-b"]

    SessionLocal = sessionmaker(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )

    # Commit setup data so both worker sessions can see it.
    with SessionLocal() as setup:
        sender = User(
            email=f"concurrent-sender-{suffix}@example.test",
            full_name="Concurrent Sender",
            password_hash="not-a-real-password-hash",
            is_active=True,
        )
        receiver = User(
            email=f"concurrent-receiver-{suffix}@example.test",
            full_name="Concurrent Receiver",
            password_hash="not-a-real-password-hash",
            is_active=True,
        )
        setup.add_all([sender, receiver])
        setup.flush()

        sender_wallet = Wallet(
            user_id=sender.id,
            currency="INR",
            available_balance=Decimal("1000.00"),
            pending_balance=Decimal("0.00"),
            status="ACTIVE",
        )
        receiver_wallet = Wallet(
            user_id=receiver.id,
            currency="INR",
            available_balance=Decimal("0.00"),
            pending_balance=Decimal("0.00"),
            status="ACTIVE",
        )
        setup.add_all([sender_wallet, receiver_wallet])
        setup.commit()

        sender_id = sender.id
        receiver_id = receiver.id
        sender_wallet_id = sender_wallet.id
        receiver_wallet_id = receiver_wallet.id

    barrier = Barrier(2)

    def attempt_transfer(key):
        # Each worker gets a distinct SQLAlchemy session/connection.
        with SessionLocal() as session:
            current_sender = session.get(User, sender_id)
            request = TransferCreateRequest(
                sender_wallet_id=sender_wallet_id,
                receiver_wallet_id=receiver_wallet_id,
                amount=amount,
            )

            barrier.wait(timeout=15)

            try:
                result = create_transfer(
                    session,
                    current_sender,
                    request,
                    idempotency_key=key,
                )
                return ("success", result)

            except HTTPException as exc:
                return ("rejected", exc.status_code, exc.detail)

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(attempt_transfer, key)
                for key in keys
            ]
            results = [future.result(timeout=30) for future in futures]

        successes = [r for r in results if r[0] == "success"]
        rejected = [r for r in results if r[0] == "rejected"]

        # One transfer succeeds; the other sees the updated balance.
        assert len(successes) == 1, results
        assert len(rejected) == 1, results
        assert rejected[0][1] == 409
        assert rejected[0][2] == "Insufficient available balance."

        with SessionLocal() as verify:
            sender_wallet = verify.get(Wallet, sender_wallet_id)
            receiver_wallet = verify.get(Wallet, receiver_wallet_id)

            assert sender_wallet.available_balance == Decimal("300.00")
            assert receiver_wallet.available_balance == Decimal("700.00")
            assert sender_wallet.available_balance >= Decimal("0.00")

            transfers = list(
                verify.scalars(
                    select(Transfer).where(
                        Transfer.sender_wallet_id == sender_wallet_id,
                        Transfer.receiver_wallet_id == receiver_wallet_id,
                    )
                ).all()
            )
            assert len(transfers) == 1

            ledger_entries = list(
                verify.scalars(
                    select(LedgerEntry).where(
                        LedgerEntry.reference_entity == "TRANSFER",
                        LedgerEntry.reference_id == transfers[0].id,
                    )
                ).all()
            )

            assert len(ledger_entries) == 2
            assert sum(
                (entry.amount for entry in ledger_entries),
                Decimal("0.00"),
            ) == Decimal("0.00")

    
    finally:
        # Ledger entries are immutable. Keep the financial records and
        # their parent users/wallets in this disposable test database.
        # Clean up only related records that are safe to delete.
        with SessionLocal() as cleanup:
            transfer_ids = list(
                cleanup.scalars(
                    select(Transfer.id).where(
                        Transfer.sender_wallet_id == sender_wallet_id,
                        Transfer.receiver_wallet_id == receiver_wallet_id,
                    )
                ).all()
            )

            if transfer_ids:
                cleanup.execute(
                    delete(Notification).where(
                        Notification.entity_type == "TRANSFER",
                        Notification.entity_id.in_(transfer_ids),
                    )
                )

                cleanup.execute(
                    delete(AuditLog).where(
                        AuditLog.entity_type == "TRANSFER",
                        AuditLog.entity_id.in_(transfer_ids),
                    )
                )

            cleanup.execute(
                delete(IdempotencyKey).where(
                    IdempotencyKey.user_id == sender_id,
                    IdempotencyKey.key.in_(keys),
                )
            )

            cleanup.commit()

