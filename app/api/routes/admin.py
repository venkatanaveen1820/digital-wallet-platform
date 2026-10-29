from fastapi import APIRouter, Depends

from app.api.deps import require_roles
from app.models import User

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.transaction_limit import (
    TransactionLimitResponse,
    TransactionLimitUpdate,
)
from app.services.transaction_limit_service import (
    get_transaction_limits,
    update_transaction_limits,
)

from app.schemas.dashboard import (
    AdminDashboardResponse,
    SupportDashboardResponse,
)
from app.services import dashboard_service


router = APIRouter(prefix="/admin", tags=["Administration"])


@router.get(
    "/dashboard",
    response_model=AdminDashboardResponse,
)
def admin_dashboard(
    current_user: User = Depends(
        require_roles("SUPER_ADMIN", "ADMIN")
    ),
    db: Session = Depends(get_db),
):
    return dashboard_service.get_admin_dashboard(db)


@router.get(
    "/support-dashboard",
    response_model=SupportDashboardResponse,
)
def support_dashboard(
    current_user: User = Depends(
        require_roles(
            "SUPER_ADMIN",
            "ADMIN",
            "SUPPORT_AGENT",
        )
    ),
    db: Session = Depends(get_db),
):
    return dashboard_service.get_support_dashboard(db)


@router.get(
    "/transaction-limits",
    response_model=TransactionLimitResponse,
)
def read_transaction_limits(
    current_user: User = Depends(
        require_roles("SUPER_ADMIN", "ADMIN")
    ),
    db: Session = Depends(get_db),
):
    return get_transaction_limits(db)


@router.patch(
    "/transaction-limits",
    response_model=TransactionLimitResponse,
)
def patch_transaction_limits(
    data: TransactionLimitUpdate,
    current_user: User = Depends(
        require_roles("SUPER_ADMIN", "ADMIN")
    ),
    db: Session = Depends(get_db),
):
    return update_transaction_limits(db, data)
