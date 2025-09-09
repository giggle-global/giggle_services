# app/routes/agreement.py
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
from app.models.agreement import (
    AgreementCreate, AgreementUpdate, AgreementSign, AgreementOut
)
from app.services.agreement import AgreementService
from app.core.keycloak import get_current_user

router = APIRouter(prefix="/agreements", tags=["agreements"])
service = AgreementService()

@router.post("/", response_model=AgreementOut)
def create_agreement(payload: AgreementCreate, current_user: dict = Depends(get_current_user)):
    return service.create_agreement(payload, current_user)

@router.put("/{agreement_id}", response_model=AgreementOut)
def update_agreement(agreement_id: str, payload: AgreementUpdate, current_user: dict = Depends(get_current_user)):
    return service.update_agreement(agreement_id, payload, current_user)

@router.post("/{agreement_id}/send", response_model=AgreementOut)
def send_agreement(agreement_id: str, current_user: dict = Depends(get_current_user)):
    return service.send_to_client(agreement_id, current_user)

@router.post("/{agreement_id}/accept", response_model=AgreementOut)
def accept_agreement(agreement_id: str, payload: AgreementSign, current_user: dict = Depends(get_current_user)):
    return service.client_accept(agreement_id, payload, current_user)

@router.post("/{agreement_id}/reject", response_model=AgreementOut)
def reject_agreement(agreement_id: str, reason: str, current_user: dict = Depends(get_current_user)):
    return service.client_reject(agreement_id, reason, current_user)

@router.get("/freelancer/{freelancer_id}", response_model=List[AgreementOut])
def list_for_freelancer(freelancer_id: str, limit: int = Query(50), skip: int = Query(0), current_user: dict = Depends(get_current_user)):
    return service.list_for_freelancer(freelancer_id, current_user, limit, skip)

@router.get("/client/{client_id}", response_model=List[AgreementOut])
def list_for_client(client_id: str, limit: int = Query(50), skip: int = Query(0), current_user: dict = Depends(get_current_user)):
    return service.list_for_client(client_id, current_user, limit, skip)

@router.get("/{agreement_id}", response_model=AgreementOut)
def get_agreement(agreement_id: str, current_user: dict = Depends(get_current_user)):
    return service.get_agreement(agreement_id, current_user)
