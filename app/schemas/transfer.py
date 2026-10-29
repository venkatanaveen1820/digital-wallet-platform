
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TransferCreateRequest(BaseModel):
    sender_wallet_id: int = Field(gt=0)
    receiver_wallet_id: int = Field(gt=0)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("Amount must be a finite number.")
        return value


class TransferResponse(BaseModel):
    id: int
    sender_wallet_id: int
    receiver_wallet_id: int
    amount: Decimal
    currency: str
    status: Literal[
        "PENDING",
        "PROCESSING",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
    ]
    reference: str
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
