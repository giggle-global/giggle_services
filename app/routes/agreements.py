# agreements/routes.py
from fastapi import APIRouter, Depends, Body, HTTPException, status
from typing import Dict, Any
from app.models.agreements import AgreementCreate, AgreementUpdate
from app.repositories.agreements import AgreementRepository
from app.services.agreements import AgreementService
from app.core.keycloak import get_current_user

router = APIRouter(prefix="/api/agreements", tags=["agreements"])

def get_agreement_service():
    return AgreementService()

@router.post("/", status_code=201)
def create_agreement(payload: AgreementCreate, current_user: Dict[str, Any] = Depends(get_current_user), svc: AgreementService = Depends(get_agreement_service)):
    if current_user["user_id"] != payload.client.user_id and current_user.get("role") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to create agreement for other client")
    created = svc.create_agreement(payload, created_by=current_user["user_id"])
    return created

@router.get("/{agreement_id}")
def get_agreement(agreement_id: str, svc: AgreementService = Depends(get_agreement_service)):
    return svc.get_agreement(agreement_id)

@router.put("/{agreement_id}")
def update_agreement(agreement_id: str, payload: AgreementUpdate, current_user: Dict[str, Any] = Depends(get_current_user), svc: AgreementService = Depends(get_agreement_service)):
    return svc.update_agreement(agreement_id, payload.model_dump(exclude_unset=True), current_user)

@router.post("/{agreement_id}/sign")
def sign_agreement(agreement_id: str, signature: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user), svc: AgreementService = Depends(get_agreement_service)):
    # signature: {"name": "John", "signature_type": "text", "signature_value": "John"}
    return svc.sign_agreement(agreement_id, current_user, signature)

@router.post("/{agreement_id}/cancel")
def cancel_agreement(agreement_id: str, payload: Dict[str, Any] = Body(None), current_user: Dict[str, Any] = Depends(get_current_user), svc: AgreementService = Depends(get_agreement_service)):
    reason = payload.get("reason") if payload else None
    return svc.cancel_agreement(agreement_id, current_user, reason)
