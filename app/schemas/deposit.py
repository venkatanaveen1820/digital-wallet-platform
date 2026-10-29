
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class DepositCreateRequest(BaseModel):
    amount: Decimal = Field(
        gt=0,
        max_digits=18,
        decimal_places=2,
    )


class DepositResponse(BaseModel):
    id: int
    wallet_id: int
    amount: Decimal
    currency: str
    status: str
    reference_number: str
    created_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
