
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WithdrawalCreateRequest(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("Amount must be finite.")

        if value.as_tuple().exponent < -2:
            raise ValueError(
                "Amount cannot have more than two decimal places."
            )

        return value


class WithdrawalResponse(BaseModel):
    id: int
    wallet_id: int
    amount: Decimal
    currency: str
    status: str
    reference_number: str
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
