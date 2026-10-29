
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TransactionLimit(Base):
    __tablename__ = "transaction_limits"

    # A singleton row with id=1 stores the active system-wide limits.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)

    max_transaction_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("50000.00")
    )
    daily_transfer_limit: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("100000.00")
    )
    daily_withdrawal_limit: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("25000.00")
    )
    max_transactions_per_day: Mapped[int] = mapped_column(
        Integer, nullable=False, default=20
    )
    suspicious_amount_threshold: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("25000.00")
    )
    rapid_transfer_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5
    )
    rapid_transfer_window_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
