from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict


class WalletCreateRequest(BaseModel):
    currency: Literal["INR"] = "INR"


class WalletResponse(BaseModel):
    id: int
    user_id: int
    currency: str
    available_balance: Decimal
    pending_balance: Decimal
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WalletStatusUpdateRequest(BaseModel):
    status: Literal["ACTIVE", "FROZEN", "SUSPENDED", "CLOSED"]