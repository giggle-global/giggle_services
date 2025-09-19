# milestones/routes.py
from fastapi import APIRouter, Depends, Body, HTTPException, status
from typing import Dict, Any
from app.repositories.milestones import MilestoneRepository
from app.services.milestones import MilestoneService
from app.repositories.agreements import AgreementRepository
from app.core.keycloak import get_current_user

router = APIRouter(prefix="/api/milestones", tags=["milestones"])

def get_milestone_service():
    return MilestoneService()

@router.post("/agreements/{agreement_id}", status_code=201)
def add_milestone(agreement_id: str, payload: Dict[str, Any], current_user: Dict[str, Any] = Depends(get_current_user), svc: MilestoneService = Depends(get_milestone_service)):
    # payload should match MilestoneCreate shape
    return svc.add_milestone(agreement_id, payload, current_user)

@router.get("/agreements/{agreement_id}")
def list_milestones(agreement_id: str, svc: MilestoneService = Depends(get_milestone_service)):
    return svc.list_for_agreement(agreement_id)

@router.put("/{milestone_id}")
def update_milestone(milestone_id: str, payload: Dict[str, Any], current_user: Dict[str, Any] = Depends(get_current_user), svc: MilestoneService = Depends(get_milestone_service)):
    return svc.update_milestone(milestone_id, payload, current_user)

@router.post("/{milestone_id}/approve")
def approve_milestone(milestone_id: str, payload: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user), svc: MilestoneService = Depends(get_milestone_service)):
    approve = payload.get("approve", True)
    notes = payload.get("notes")
    return svc.approve_milestone(milestone_id, current_user, approve, notes)

@router.delete("/{milestone_id}")
def delete_milestone(milestone_id: str, current_user: Dict[str, Any] = Depends(get_current_user), svc: MilestoneService = Depends(get_milestone_service)):
    return svc.delete_milestone(milestone_id, current_user)
