import hashlib
import json
import secrets
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import (
    IdempotencyKey,
    LedgerEntry,
    Transfer,
    User,
    Wallet,
)
from app.repositories import transfer_repository
from app.schemas.transfer import TransferCreateRequest
from app.services.audit_log_service import create_audit_log
from app.services.notification_service import create_notification


MAX_BALANCE = Decimal("9999999999999999.99")
OPERATION = "TRANSFER_CREATE"


def _request_hash(data: TransferCreateRequest) -> str:
    payload = {
        "sender_wallet_id": data.sender_wallet_id,
        "receiver_wallet_id": data.receiver_wallet_id,
        "amount": format(data.amount, "f"),
    }

    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def create_transfer(
    db: Session,
    current_user: User,
    data: TransferCreateRequest,
    idempotency_key: str,
) -> dict:
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

    if data.sender_wallet_id == data.receiver_wallet_id:
        raise HTTPException(
            status_code=422,
            detail="Sender and receiver wallets must be different.",
        )

    if not idempotency_key or len(idempotency_key) > 255:
        raise HTTPException(
            status_code=400,
            detail="Provide a valid Idempotency-Key header.",
        )

    request_hash = _request_hash(data)

    try:
        # Atomically claim the idempotency key.
        claim = (
            insert(IdempotencyKey)
            .values(
                user_id=current_user.id,
                operation=OPERATION,
                key=idempotency_key,
                request_hash=request_hash,
            )
            .on_conflict_do_nothing(
                constraint="uq_idempotency_user_operation_key"
            )
            .returning(IdempotencyKey.id)
        )

        claimed_id = db.scalar(claim)

        if claimed_id is None:
            existing = db.scalar(
                select(IdempotencyKey)
                .where(
                    IdempotencyKey.user_id == current_user.id,
                    IdempotencyKey.operation == OPERATION,
                    IdempotencyKey.key == idempotency_key,
                )
                .with_for_update()
            )

            if existing is None:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Idempotency key is being processed. "
                        "Retry shortly."
                    ),
                )

            if existing.request_hash != request_hash:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "This Idempotency-Key was already used "
                        "for a different request."
                    ),
                )

            if (
                existing.response_status is None
                or existing.response_body is None
            ):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "The previous request has no stored response. "
                        "Retry with a new key."
                    ),
                )

            response = existing.response_body
            db.commit()
            return response

        # Lock both wallets in ascending ID order to reduce deadlocks.
        wallets = transfer_repository.lock_wallets(
            db,
            [data.sender_wallet_id, data.receiver_wallet_id],
        )
        wallet_by_id = {wallet.id: wallet for wallet in wallets}

        sender = wallet_by_id.get(data.sender_wallet_id)
        receiver = wallet_by_id.get(data.receiver_wallet_id)

        if sender is None or sender.user_id != current_user.id:
            raise HTTPException(
                status_code=404,
                detail="Sender wallet not found.",
            )

        if receiver is None:
            raise HTTPException(
                status_code=404,
                detail="Receiver wallet not found.",
            )

        if sender.user_id == receiver.user_id:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Transfers between wallets belonging to the same "
                    "user are not allowed."
                ),
            )

        if sender.status != "ACTIVE" or receiver.status != "ACTIVE":
            raise HTTPException(
                status_code=409,
                detail="Both wallets must be active to transfer funds.",
            )

        if sender.currency != receiver.currency:
            raise HTTPException(
                status_code=409,
                detail="Sender and receiver wallet currencies must match.",
            )

        if amount.adjusted() > 15:
            raise HTTPException(
                status_code=422,
                detail="Amount exceeds the supported transfer limit.",
            )

        if sender.available_balance < amount:
            raise HTTPException(
                status_code=409,
                detail="Insufficient available balance.",
            )

        if receiver.available_balance + amount > MAX_BALANCE:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Transfer would exceed the receiver's "
                    "supported balance."
                ),
            )

        sender_before = sender.available_balance
        receiver_before = receiver.available_balance
        sender_after = sender_before - amount
        receiver_after = receiver_before + amount
        now = datetime.now(timezone.utc)

        transfer = Transfer(
            sender_wallet_id=sender.id,
            receiver_wallet_id=receiver.id,
            amount=amount,
            currency=sender.currency,
            status="COMPLETED",
            reference=f"TRF-{secrets.token_hex(16).upper()}",
            completed_at=now,
        )

        # Obtain the transfer ID before creating ledger entries.
        transfer_repository.create_transfer(db, transfer)

        sender.available_balance = sender_after
        receiver.available_balance = receiver_after

        db.add_all(
            [
                LedgerEntry(
                    wallet_id=sender.id,
                    transaction_type="TRANSFER_DEBIT",
                    amount=-amount,
                    balance_before=sender_before,
                    balance_after=sender_after,
                    reference_entity="TRANSFER",
                    reference_id=transfer.id,
                    description=f"Transfer to wallet {receiver.id}",
                    created_by=current_user.id,
                    metadata_json={"currency": sender.currency},
                ),
                LedgerEntry(
                    wallet_id=receiver.id,
                    transaction_type="TRANSFER_CREDIT",
                    amount=amount,
                    balance_before=receiver_before,
                    balance_after=receiver_after,
                    reference_entity="TRANSFER",
                    reference_id=transfer.id,
                    description=f"Transfer from wallet {sender.id}",
                    created_by=current_user.id,
                    metadata_json={"currency": receiver.currency},
                ),
            ]
        )

        db.flush()
        db.refresh(transfer)

        response = {
            "id": transfer.id,
            "sender_wallet_id": transfer.sender_wallet_id,
            "receiver_wallet_id": transfer.receiver_wallet_id,
            "amount": str(transfer.amount),
            "currency": transfer.currency,
            "status": transfer.status,
            "reference": transfer.reference,
            "completed_at": (
                transfer.completed_at.isoformat()
                if transfer.completed_at
                else None
            ),
            "created_at": transfer.created_at.isoformat(),
            "updated_at": transfer.updated_at.isoformat(),
        }

        create_audit_log(
            db,
            user_id=current_user.id,
            action="TRANSFER_COMPLETED",
            entity_type="TRANSFER",
            entity_id=transfer.id,
            metadata={
                "amount": str(amount),
                "currency": sender.currency,
                "sender_wallet_id": sender.id,
                "receiver_wallet_id": receiver.id,
                "status": transfer.status,
            },
        )

        create_notification(
            db,
            user_id=sender.user_id,
            event_type="TRANSFER_SENT",
            title="Transfer completed",
            message=(
                f"Your transfer of {amount} {sender.currency} "
                f"to wallet {receiver.id} completed successfully."
            ),
            entity_type="TRANSFER",
            entity_id=transfer.id,
        )

        create_notification(
            db,
            user_id=receiver.user_id,
            event_type="TRANSFER_RECEIVED",
            title="Money received",
            message=(
                f"You received {amount} {receiver.currency} "
                f"from wallet {sender.id}."
            ),
            entity_type="TRANSFER",
            entity_id=transfer.id,
        )

        idempotency_record = db.get(IdempotencyKey, claimed_id)
        idempotency_record.response_status = 201
        idempotency_record.response_body = response

        # Transfer, balances, ledger, audit, notifications, and the
        # idempotency response commit together.
        db.commit()
        return response

    except Exception:
        db.rollback()
        raise