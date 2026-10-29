
from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.core.config import settings
from app.api.routes.admin import router as admin_router
from app.api.routes.admin_users import router as admin_users_router
from app.api.routes.wallets import router as wallets_router
from app.api.routes.deposits import router as deposits_router
from app.api.routes.transfers import router as transfers_router
from app.api.routes.withdrawals import router as withdrawals_router
from app.api.routes.refunds import router as refunds_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.audit_logs import router as audit_logs_router
from app.api.routes.dashboard import router as dashboard_router


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Digital Wallet and Transaction Processing Platform",
)

app.include_router(
    auth_router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    admin_router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    admin_users_router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    wallets_router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    deposits_router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    transfers_router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    withdrawals_router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    refunds_router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    notifications_router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    audit_logs_router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    dashboard_router,
    prefix=settings.API_V1_PREFIX,
)

@app.get("/health", tags=["Health"])
def health_check():
    return {
        "success": True,
        "message": "Digital Wallet API is running.",
    }
