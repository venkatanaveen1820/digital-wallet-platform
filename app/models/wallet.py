
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Wallet(TimestampMixin, Base):
    __tablename__ = "wallets"

    __table_args__ = (
        CheckConstraint(
            "available_balance >= 0",
            name="ck_wallets_available_balance_nonnegative",
        ),
        CheckConstraint(
            "pending_balance >= 0",
            name="ck_wallets_pending_balance_nonnegative",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'FROZEN', 'SUSPENDED', 'CLOSED')",
            name="ck_wallets_valid_status",
        ),
        Index("ix_wallets_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
        server_default="INR",
    )

    available_balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    pending_balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    status: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="ACTIVE",
        server_default="ACTIVE",
    )

    owner = relationship("User", backref="wallets")
