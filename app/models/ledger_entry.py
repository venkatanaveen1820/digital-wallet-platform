
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    JSON,
    Numeric,
    String,
    DateTime,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    __table_args__ = (
        CheckConstraint(
            "amount <> 0",
            name="ck_ledger_entries_amount_nonzero",
        ),
        CheckConstraint(
            "balance_before >= 0 AND balance_after >= 0",
            name="ck_ledger_entries_balances_nonnegative",
        ),
        CheckConstraint(
            "transaction_type IN ('DEPOSIT', 'WITHDRAWAL', "
            "'TRANSFER_DEBIT', 'TRANSFER_CREDIT', 'REFUND', "
            "'FEE', 'ADJUSTMENT', 'REVERSAL')",
            name="ck_ledger_entries_valid_type",
        ),
        Index(
            "ix_ledger_entries_wallet_created",
            "wallet_id",
            "created_at",
        ),
        Index(
            "ix_ledger_entries_reference",
            "reference_entity",
            "reference_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    wallet_id: Mapped[int] = mapped_column(
        ForeignKey("wallets.id", ondelete="RESTRICT"),
        nullable=False,
    )

    transaction_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )

    balance_before: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )

    balance_after: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )

    reference_entity: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    reference_id: Mapped[int] = mapped_column(
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    metadata_json: Mapped[dict] = mapped_column(
        "metadata",
        JSON,
        nullable=False,
        default=dict,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    wallet = relationship("Wallet")
