import secrets
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import LedgerEntry, Refund, Transfer, User, Wallet
from app.repositories import refund_repository
from app.schemas.refund import RefundCreateRequest, RefundRejectRequest
from app.services.audit_log_service import create_audit_log
from app.services.notification_service import create_notification


PRIVILEGED_ROLES = {"SUPER_ADMIN", "ADMIN", "SUPPORT_AGENT"}
MAX_BALANCE = Decimal("9999999999999999.99")
REVIEWABLE_STATUSES = {"REQUESTED", "UNDER_REVIEW"}


def _has_privileged_role(user: User) -> bool:
    return bool(
        {role.name for role in user.roles}
        & PRIVILEGED_ROLES
    )


def _require_reviewer(user: User) -> None:
    if not _has_privileged_role(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Only administrators or support agents "
                "can review refunds."
            ),
        )


def _get_transfer_and_wallets(
    db: Session,
    transfer_id: int,
    *,
    lock: bool,
) -> tuple[Transfer | None, Wallet | None, Wallet | None]:
    transfer_statement = select(Transfer).where(
        Transfer.id == transfer_id
    )

    if lock:
        transfer_statement = transfer_statement.with_for_update()

    transfer = db.scalar(transfer_statement)

    if transfer is None:
        return None, None, None

    wallet_statement = (
        select(Wallet)
        .where(
            Wallet.id.in_(
                [
                    transfer.sender_wallet_id,
                    transfer.receiver_wallet_id,
                ]
            )
        )
        .order_by(Wallet.id)
    )

    if lock:
        wallet_statement = wallet_statement.with_for_update()

    wallets = list(db.scalars(wallet_statement).all())
    by_id = {wallet.id: wallet for wallet in wallets}

    return (
        transfer,
        by_id.get(transfer.sender_wallet_id),
        by_id.get(transfer.receiver_wallet_id),
    )


def _validate_transfer_and_wallets(
    transfer: Transfer | None,
    sender: Wallet | None,
    receiver: Wallet | None,
) -> None:
    if transfer is None or sender is None or receiver is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Completed transfer not found.",
        )

    if transfer.status != "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only completed transfers can be refunded.",
        )

    if sender.status == "CLOSED" or receiver.status == "CLOSED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Refunds are not allowed when either wallet is closed.",
        )

    if (
        sender.currency != receiver.currency
        or transfer.currency != sender.currency
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transfer and wallet currencies do not match.",
        )


def create_refund(
    db: Session,
    current_user: User,
    data: RefundCreateRequest,
) -> Refund:
    try:
        # Lock the transfer so concurrent refund requests cannot
        # reserve more than the original transfer amount.
        transfer, sender, receiver = _get_transfer_and_wallets(
            db,
            data.transfer_id,
            lock=True,
        )

        _validate_transfer_and_wallets(
            transfer,
            sender,
            receiver,
        )

        if sender.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Completed transfer not found.",
            )

        if (
            not data.amount.is_finite()
            or data.amount <= Decimal("0")
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Refund amount must be a positive, finite value.",
            )

        if data.amount.as_tuple().exponent < -2:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Refund amount cannot have more than "
                    "two decimal places."
                ),
            )

        already_reserved = refund_repository.sum_reserved_for_transfer(
            db,
            transfer.id,
        )
        remaining = transfer.amount - already_reserved

        if data.amount > remaining:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Refund amount exceeds the remaining refundable "
                    f"amount of {remaining} {transfer.currency}."
                ),
            )

        refund = Refund(
            transfer_id=transfer.id,
            requested_by=current_user.id,
            amount=data.amount,
            currency=transfer.currency,
            status="REQUESTED",
            reference=f"REF-{secrets.token_hex(12).upper()}",
            reason=data.reason,
        )

        refund_repository.add(db, refund)
        db.flush()

        create_audit_log(
            db,
            user_id=current_user.id,
            action="REFUND_CREATED",
            entity_type="REFUND",
            entity_id=refund.id,
            metadata={
                "transfer_id": transfer.id,
                "amount": str(refund.amount),
                "currency": refund.currency,
                "status": refund.status,
            },
        )

        create_notification(
            db,
            user_id=current_user.id,
            event_type="REFUND_REQUESTED",
            title="Refund request submitted",
            message=(
                f"Your refund request for {refund.amount} "
                f"{refund.currency} was submitted for review."
            ),
            entity_type="REFUND",
            entity_id=refund.id,
        )

        db.commit()
        db.refresh(refund)
        return refund

    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The refund request conflicts with an existing record.",
        ) from exc

    except Exception:
        db.rollback()
        raise


def list_refunds(
    db: Session,
    current_user: User,
) -> list[Refund]:
    if _has_privileged_role(current_user):
        return refund_repository.list_all(db)

    return refund_repository.list_for_user(
        db,
        current_user.id,
    )


def get_refund(
    db: Session,
    current_user: User,
    refund_id: int,
) -> Refund:
    refund = refund_repository.get_by_id(
        db,
        refund_id,
    )

    if refund is None or (
        not _has_privileged_role(current_user)
        and refund.requested_by != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Refund not found.",
        )

    return refund


def approve_refund(
    db: Session,
    reviewer: User,
    refund_id: int,
) -> Refund:
    _require_reviewer(reviewer)

    try:
        refund = refund_repository.get_by_id(
            db,
            refund_id,
            for_update=True,
        )

        if refund is None:
            raise HTTPException(
                status_code=404,
                detail="Refund not found.",
            )

        if refund.status not in REVIEWABLE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Refund cannot be approved from status "
                    f"{refund.status}."
                ),
            )

        transfer, sender, receiver = _get_transfer_and_wallets(
            db,
            refund.transfer_id,
            lock=True,
        )

        _validate_transfer_and_wallets(
            transfer,
            sender,
            receiver,
        )

        if (
            sender.currency != refund.currency
            or receiver.currency != refund.currency
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Refund and wallet currencies do not match.",
            )

        reserved_total = refund_repository.sum_reserved_for_transfer(
            db,
            transfer.id,
        )

        if reserved_total > transfer.amount:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Total refund requests exceed the original "
                    "transfer amount."
                ),
            )

        if receiver.available_balance < refund.amount:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The original receiver has insufficient funds "
                    "for this refund."
                ),
            )

        if sender.available_balance + refund.amount > MAX_BALANCE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Refund would exceed the sender wallet's "
                    "supported balance."
                ),
            )

        receiver_before = receiver.available_balance
        sender_before = sender.available_balance

        receiver_after = receiver_before - refund.amount
        sender_after = sender_before + refund.amount
        now = datetime.now(timezone.utc)

        # Settlement, ledger entries, audit record and notification
        # all participate in this transaction.
        refund.status = "APPROVED"
        refund.reviewed_by = reviewer.id
        refund.reviewed_at = now

        receiver.available_balance = receiver_after
        sender.available_balance = sender_after

        db.add_all(
            [
                LedgerEntry(
                    wallet_id=receiver.id,
                    transaction_type="REVERSAL",
                    amount=-refund.amount,
                    balance_before=receiver_before,
                    balance_after=receiver_after,
                    reference_entity="REFUND",
                    reference_id=refund.id,
                    description=(
                        f"Refund {refund.reference}: return transfer "
                        f"to sender wallet {sender.id}"
                    ),
                    created_by=reviewer.id,
                    metadata_json={
                        "transfer_id": transfer.id,
                        "refund_reference": refund.reference,
                    },
                ),
                LedgerEntry(
                    wallet_id=sender.id,
                    transaction_type="REFUND",
                    amount=refund.amount,
                    balance_before=sender_before,
                    balance_after=sender_after,
                    reference_entity="REFUND",
                    reference_id=refund.id,
                    description=(
                        f"Refund {refund.reference}: returned from "
                        f"receiver wallet {receiver.id}"
                    ),
                    created_by=reviewer.id,
                    metadata_json={
                        "transfer_id": transfer.id,
                        "refund_reference": refund.reference,
                    },
                ),
            ]
        )

        refund.status = "COMPLETED"
        refund.completed_at = now

        create_audit_log(
            db,
            user_id=reviewer.id,
            action="REFUND_COMPLETED",
            entity_type="REFUND",
            entity_id=refund.id,
            metadata={
                "transfer_id": transfer.id,
                "amount": str(refund.amount),
                "currency": refund.currency,
                "requester_id": refund.requested_by,
                "status": refund.status,
            },
        )

        create_notification(
            db,
            user_id=refund.requested_by,
            event_type="REFUND_COMPLETED",
            title="Refund completed",
            message=(
                f"Your refund of {refund.amount} "
                f"{refund.currency} has been completed."
            ),
            entity_type="REFUND",
            entity_id=refund.id,
        )

        db.commit()
        db.refresh(refund)
        return refund

    except Exception:
        db.rollback()
        raise


def reject_refund(
    db: Session,
    reviewer: User,
    refund_id: int,
    data: RefundRejectRequest,
) -> Refund:
    _require_reviewer(reviewer)

    try:
        refund = refund_repository.get_by_id(
            db,
            refund_id,
            for_update=True,
        )

        if refund is None:
            raise HTTPException(
                status_code=404,
                detail="Refund not found.",
            )

        if refund.status not in REVIEWABLE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Refund cannot be rejected from status "
                    f"{refund.status}."
                ),
            )

        refund.status = "REJECTED"
        refund.reviewed_by = reviewer.id
        refund.reviewed_at = datetime.now(timezone.utc)
        refund.rejection_reason = data.reason

        create_audit_log(
            db,
            user_id=reviewer.id,
            action="REFUND_REJECTED",
            entity_type="REFUND",
            entity_id=refund.id,
            metadata={
                "requester_id": refund.requested_by,
                "status": refund.status,
                "reason": data.reason,
            },
        )

        create_notification(
            db,
            user_id=refund.requested_by,
            event_type="REFUND_REJECTED",
            title="Refund request rejected",
            message=f"Your refund request {refund.id} was rejected.",
            entity_type="REFUND",
            entity_id=refund.id,
        )

        db.commit()
        db.refresh(refund)
        return refund

    except Exception:
        db.rollback()
        raise