# agreements/routes.py
from fastapi import APIRouter, Depends, Body, HTTPException, status
from typing import Dict, Any, Optional
from app.models.agreements import AgreementCreate, AgreementUpdate, AgreementFilter
from app.services.agreements import AgreementService
from app.core.keycloak import get_current_user
from app.schemas.response import ok, APIResponse

router = APIRouter(prefix="/api/agreements", tags=["agreements"])

def get_agreement_service():
    return AgreementService()

@router.post("/", response_model=APIResponse, status_code=201)
def create_agreement(
    payload: AgreementCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: AgreementService = Depends(get_agreement_service),
):
    # Allow both client and freelancer to create agreements, or admin
    is_client = current_user["user_id"] == payload.client.user_id
    is_freelancer = current_user["user_id"] == payload.freelancer.user_id
    is_admin = current_user.get("role") == "admin"
    
    if not (is_client or is_freelancer or is_admin):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Not allowed to create agreement. Only the client, freelancer, or admin can create agreements.",
        )
    created = svc.create_agreement(payload, created_by=current_user["user_id"])
    return ok(created, "Agreement created", status.HTTP_201_CREATED)

@router.get("/{agreement_id}", response_model=APIResponse)
def get_agreement(
    agreement_id: str,
    svc: AgreementService = Depends(get_agreement_service),
):
    agreement = svc.get_agreement(agreement_id)
    return ok(agreement, "Agreement fetched", status.HTTP_200_OK)

@router.post("/filtered", response_model=APIResponse)
def get_agreements_filtered(
    filter: AgreementFilter = Body(...),
    svc: AgreementService = Depends(get_agreement_service),
    user: Dict[str, Any] = Depends(get_current_user),
):
    result = svc.get_agreement_filtered(filter)
    return ok(result, "Agreements fetched", status.HTTP_200_OK)

@router.put("/{agreement_id}", response_model=APIResponse)
def update_agreement(
    agreement_id: str,
    payload: AgreementUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: AgreementService = Depends(get_agreement_service),
):
    updated = svc.update_agreement(agreement_id, payload.model_dump(exclude_unset=True), current_user)
    return ok(updated, "Agreement updated", status.HTTP_200_OK)

@router.post("/{agreement_id}/sign", response_model=APIResponse)
def sign_agreement(
    agreement_id: str,
    signature: Dict[str, Any] = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: AgreementService = Depends(get_agreement_service),
):
    # signature: {"name": "John", "signature_type": "text", "signature_value": "John"}
    signed = svc.sign_agreement(agreement_id, current_user, signature)
    return ok(signed, "Agreement signed", status.HTTP_200_OK)

@router.post("/{agreement_id}/cancel", response_model=APIResponse)
def cancel_agreement(
    agreement_id: str,
    payload: Optional[Dict[str, Any]] = Body(None),
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: AgreementService = Depends(get_agreement_service),
):
    reason = payload.get("reason") if payload else None
    canceled = svc.cancel_agreement(agreement_id, current_user, reason)
    return ok(canceled, "Agreement canceled", status.HTTP_200_OK)

@router.post("/{agreement_id}/pause", response_model=APIResponse)
def pause_agreement(
    agreement_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: AgreementService = Depends(get_agreement_service),
):
    paused = svc.pause_agreement(agreement_id, current_user)
    return ok(paused, "Agreement paused", status.HTTP_200_OK)

@router.post("/{agreement_id}/unpause", response_model=APIResponse)
def unpause_agreement(
    agreement_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: AgreementService = Depends(get_agreement_service),
):
    unpaused = svc.unpause_agreement(agreement_id, current_user)
    return ok(unpaused, "Agreement unpaused", status.HTTP_200_OK)

@router.post("/{agreement_id}/accept-version", response_model=APIResponse)
def accept_agreement_version(
    agreement_id: str,
    payload: Dict[str, Any] = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: AgreementService = Depends(get_agreement_service),
):
    # payload: {"accepted": true/false}
    accepted = svc.accept_agreement_version(agreement_id, current_user, payload.get("accepted", False))
    return ok(accepted, "Agreement version acceptance updated", status.HTTP_200_OK)