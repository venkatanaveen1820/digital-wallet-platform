from datetime import datetime
from pydantic import BaseModel, ConfigDict


class CurrencyAmount(BaseModel):
    currency: str
    amount: str


class RecentTransaction(BaseModel):
    transaction_type: str
    transaction_id: int
    amount: str
    currency: str
    status: str
    created_at: datetime


class AdminDashboardResponse(BaseModel):
    total_users: int
    active_wallets: int
    total_wallet_balance: list[CurrencyAmount]
    todays_transactions: int
    todays_transaction_volume: list[CurrencyAmount]
    failed_transactions: int
    suspicious_transactions: int


class SupportDashboardResponse(BaseModel):
    pending_reviews: int
    suspicious_transactions: int
    failed_transactions: int
    refund_requests: int
    frozen_wallets: int


class CustomerDashboardResponse(BaseModel):
    wallet_balance: list[CurrencyAmount]
    recent_transactions: list[RecentTransaction]
    total_deposits: list[CurrencyAmount]
    total_transfers: list[CurrencyAmount]
    total_withdrawals: list[CurrencyAmount]
    pending_transactions: int

    model_config = ConfigDict(from_attributes=True)