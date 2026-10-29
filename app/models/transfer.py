
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Transfer(TimestampMixin, Base):
    __tablename__ = "transfers"

    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="ck_transfers_amount_positive",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'CANCELLED')",
            name="ck_transfers_valid_status",
        ),
        UniqueConstraint(
            "reference",
            name="uq_transfers_reference",
        ),
        Index("ix_transfers_sender_wallet_id", "sender_wallet_id"),
        Index("ix_transfers_receiver_wallet_id", "receiver_wallet_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    sender_wallet_id: Mapped[int] = mapped_column(
        ForeignKey("wallets.id", ondelete="RESTRICT"),
        nullable=False,
    )

    receiver_wallet_id: Mapped[int] = mapped_column(
        ForeignKey("wallets.id", ondelete="RESTRICT"),
        nullable=False,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(12),
        nullable=False,
        default="PENDING",
        server_default="PENDING",
    )

    reference: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    sender_wallet = relationship(
        "Wallet",
        foreign_keys=[sender_wallet_id],
    )

    receiver_wallet = relationship(
        "Wallet",
        foreign_keys=[receiver_wallet_id],
    )
