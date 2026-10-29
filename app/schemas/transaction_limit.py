
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TransactionLimitUpdate(BaseModel):
    max_transaction_amount: Decimal | None = Field(
        default=None, gt=0, max_digits=18, decimal_places=2
    )
    daily_transfer_limit: Decimal | None = Field(
        default=None, gt=0, max_digits=18, decimal_places=2
    )
    daily_withdrawal_limit: Decimal | None = Field(
        default=None, gt=0, max_digits=18, decimal_places=2
    )
    max_transactions_per_day: int | None = Field(default=None, ge=1, le=10000)
    suspicious_amount_threshold: Decimal | None = Field(
        default=None, gt=0, max_digits=18, decimal_places=2
    )
    rapid_transfer_count: int | None = Field(default=None, ge=2, le=10000)
    rapid_transfer_window_minutes: int | None = Field(
        default=None, ge=1, le=1440
    )

    @model_validator(mode="after")
    def reject_empty_update(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one transaction limit to update.")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Transaction limit values cannot be null.")
        return self


class TransactionLimitResponse(BaseModel):
    id: int
    max_transaction_amount: Decimal
    daily_transfer_limit: Decimal
    daily_withdrawal_limit: Decimal
    max_transactions_per_day: int
    suspicious_amount_threshold: Decimal
    rapid_transfer_count: int
    rapid_transfer_window_minutes: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
