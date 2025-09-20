# milestones/routes.py
from fastapi import APIRouter, Depends, Body, HTTPException, status
from typing import Dict, Any
from app.repositories.milestones import MilestoneRepository
from app.models.milestones import MilestoneCreate, MilestoneInDB, MilestoneUpdate
from app.services.milestones import MilestoneService
from app.repositories.agreements import AgreementRepository
from app.core.keycloak import get_current_user
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/milestones", tags=["milestones"])

def get_milestone_service():
    return MilestoneService()

# ➤ Create milestone
@router.post("/agreements/{agreement_id}", response_model=MilestoneInDB, status_code=201)
def add_milestone(
    agreement_id: str,
    payload: MilestoneCreate,   # ✅ Proper model instead of Dict
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: MilestoneService = Depends(get_milestone_service),
):
    return svc.add_milestone(agreement_id, payload, current_user)


# ➤ List milestones
@router.get("/agreements/{agreement_id}", response_model=list[MilestoneInDB])
def list_milestones(
    agreement_id: str,
    svc: MilestoneService = Depends(get_milestone_service),
):
    return svc.list_for_agreement(agreement_id)


# ➤ Update milestone
@router.put("/{milestone_id}", response_model=MilestoneInDB)
def update_milestone(
    milestone_id: str,
    payload: MilestoneUpdate,   # ✅ Proper model
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: MilestoneService = Depends(get_milestone_service),
):
    return svc.update_milestone(milestone_id, payload, current_user)


# ➤ Approve milestone
class MilestoneApprovalRequest(BaseModel):
    approve: bool = True
    notes: Optional[str] = None

@router.post("/{milestone_id}/approve", response_model=MilestoneInDB)
def approve_milestone(
    milestone_id: str,
    payload: MilestoneApprovalRequest,   # ✅ Proper model
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: MilestoneService = Depends(get_milestone_service),
):
    return svc.approve_milestone(milestone_id, current_user, payload.approve, payload.notes)

# @router.delete("/{milestone_id}")
# def delete_milestone(milestone_id: str, current_user: Dict[str, Any] = Depends(get_current_user), svc: MilestoneService = Depends(get_milestone_service)):
#     return svc.delete_milestone(milestone_id, current_user)
