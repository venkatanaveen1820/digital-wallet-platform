from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RefundCreateRequest(BaseModel):
    transfer_id: int = Field(gt=0)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("Refund amount must be finite.")
        if value.as_tuple().exponent < -2:
            raise ValueError("Refund amount cannot have more than two decimal places.")
        return value

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class RefundRejectRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("A rejection reason of at least 3 characters is required.")
        return value


class RefundResponse(BaseModel):
    id: int
    transfer_id: int
    requested_by: int
    reviewed_by: int | None
    amount: Decimal
    currency: str
    status: str
    reference: str
    reason: str | None
    rejection_reason: str | None
    reviewed_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
