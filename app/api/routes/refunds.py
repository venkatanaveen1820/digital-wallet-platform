from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.refund import (
    RefundCreateRequest,
    RefundRejectRequest,
    RefundResponse,
)
from app.services import refund_service

router = APIRouter(tags=["Refunds"])


@router.post(
    "/refunds",
    response_model=RefundResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_refund(
    data: RefundCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Request a full or partial refund for a completed transfer."""
    return refund_service.create_refund(db, current_user, data)


@router.get("/refunds", response_model=list[RefundResponse])
def list_refunds(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List refunds visible to the authenticated user."""
    return refund_service.list_refunds(db, current_user)


@router.get("/refunds/{refund_id}", response_model=RefundResponse)
def get_refund(
    refund_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve a refund by its ID."""
    return refund_service.get_refund(db, current_user, refund_id)


@router.post(
    "/refunds/{refund_id}/approve",
    response_model=RefundResponse,
)
def approve_refund(
    refund_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Approve and settle a refund. Restricted to privileged roles."""
    return refund_service.approve_refund(db, current_user, refund_id)


@router.post(
    "/refunds/{refund_id}/reject",
    response_model=RefundResponse,
)
def reject_refund(
    refund_id: int,
    data: RefundRejectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reject a refund request and record the reason."""
    return refund_service.reject_refund(
        db, current_user, refund_id, data
    )