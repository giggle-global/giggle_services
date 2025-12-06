# milestones/routes.py
from fastapi import APIRouter, Depends, Body, HTTPException, status
from typing import Dict, Any, Optional
from pydantic import BaseModel

from app.models.milestones import MilestoneCreate, MilestoneUpdate
from app.services.milestones import MilestoneService
from app.core.keycloak import get_current_user
from app.schemas.response import ok, APIResponse

router = APIRouter(prefix="/api/milestones", tags=["milestones"])

def get_milestone_service():
    return MilestoneService()


# ➤ Create milestone
@router.post("/agreements/{agreement_id}", response_model=APIResponse, status_code=201)
def add_milestone(
    agreement_id: str,
    payload: MilestoneCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: MilestoneService = Depends(get_milestone_service),
):
    created = svc.add_milestone(agreement_id, payload, current_user)
    return ok(created, "Milestone created", status.HTTP_201_CREATED)


# ➤ List milestones
@router.get("/agreements/{agreement_id}", response_model=APIResponse)
def list_milestones(
    agreement_id: str,
    svc: MilestoneService = Depends(get_milestone_service),
):
    milestones = svc.list_for_agreement(agreement_id)
    return ok(milestones, "Milestones fetched", status.HTTP_200_OK)


# ➤ Update milestone
@router.put("/{milestone_id}", response_model=APIResponse)
def update_milestone(
    milestone_id: str,
    payload: MilestoneUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: MilestoneService = Depends(get_milestone_service),
):
    print("Updating milestone:", milestone_id, payload)
    updated = svc.update_milestone(milestone_id, payload, current_user)
    return ok(updated, "Milestone updated", status.HTTP_200_OK)


# ➤ Approve milestone
class MilestoneApprovalRequest(BaseModel):
    approve: bool = True
    notes: Optional[str] = None

@router.post("/{milestone_id}/approve", response_model=APIResponse)
def approve_milestone(
    milestone_id: str,
    payload: MilestoneApprovalRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: MilestoneService = Depends(get_milestone_service),
):
    approved = svc.approve_milestone(milestone_id, current_user, payload.approve, payload.notes)
    return ok(approved, "Milestone approval updated", status.HTTP_200_OK)


# ➤ Verify milestone (Freelancer)
@router.post("/{milestone_id}/verify", response_model=APIResponse)
def verify_milestone(
    milestone_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: MilestoneService = Depends(get_milestone_service),
):
    verified = svc.verify_milestone(milestone_id, current_user)
    return ok(verified, "Milestone verified", status.HTTP_200_OK)


# ➤ Complete milestone (Client)
@router.post("/{milestone_id}/complete", response_model=APIResponse)
def complete_milestone(
    milestone_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: MilestoneService = Depends(get_milestone_service),
):
    completed = svc.complete_milestone(milestone_id, current_user)
    return ok(completed, "Milestone completed", status.HTTP_200_OK)


# ➤ Send payment (Client)
@router.post("/{milestone_id}/payment/send", response_model=APIResponse)
def send_payment(
    milestone_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: MilestoneService = Depends(get_milestone_service),
):
    result = svc.send_payment(milestone_id, current_user)
    return ok(result, "Payment marked as sent", status.HTTP_200_OK)


# ➤ Receive payment (Freelancer)
@router.post("/{milestone_id}/payment/receive", response_model=APIResponse)
def receive_payment(
    milestone_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: MilestoneService = Depends(get_milestone_service),
):
    result = svc.receive_payment(milestone_id, current_user)
    return ok(result, "Payment marked as received", status.HTTP_200_OK)


# ➤ Delete milestone
@router.delete("/{milestone_id}", response_model=APIResponse)
def delete_milestone(
    milestone_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: MilestoneService = Depends(get_milestone_service),
):
    deleted = svc.delete_milestone(milestone_id, current_user)
    return ok(deleted, "Milestone deleted", status.HTTP_200_OK)
