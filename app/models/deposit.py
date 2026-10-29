
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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Deposit(TimestampMixin, Base):
    __tablename__ = "deposits"

    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="ck_deposits_amount_positive",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'CANCELLED')",
            name="ck_deposits_valid_status",
        ),
        UniqueConstraint(
            "reference_number",
            name="uq_deposits_reference_number",
        ),
        Index("ix_deposits_wallet_id", "wallet_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    wallet_id: Mapped[int] = mapped_column(
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
        default="COMPLETED",
        server_default="COMPLETED",
    )

    reference_number: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    wallet = relationship("Wallet", backref="deposits")
