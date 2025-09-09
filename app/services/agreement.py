# app/services/agreement.py
from typing import List, Dict, Any
from fastapi import HTTPException
from app.repositories.agreement import AgreementRepository
from app.models.agreement import (
    AgreementCreate, AgreementUpdate, AgreementSign, AgreementStatus,
    TimelineEntry, TimelineAction
)
import time

class AgreementService:
    def __init__(self, repo: AgreementRepository = None):
        self.repo = repo or AgreementRepository()

    def _compute_total(self, milestones: List[Dict]) -> float:
        if not milestones:
            return 0.0
        return float(sum(m.get("amount", 0) for m in milestones))

    def create_agreement(self, payload: AgreementCreate, current_user: dict) -> dict:
        # Only freelancer can create agreements
        if current_user.get("role") != "FL":
            raise HTTPException(status_code=403, detail="Only freelancers can create agreements")
        if current_user.get("user_id") != payload.freelancer_id:
            raise HTTPException(status_code=403, detail="Freelancer id mismatch")

        data = payload.model_dump()
        # compute total
        total = self._compute_total(data.get("milestones", []))
        data["total_amount"] = total
        # initialize timeline with created entry
        entry = TimelineEntry(action=TimelineAction.CREATED, user_id=current_user["user_id"], user_role=current_user["role"], note="Agreement created").model_dump()
        data["timeline"] = [entry]
        data["status"] = AgreementStatus.DRAFT.value
        return self.repo.create(data)

    def update_agreement(self, agreement_id: str, update: AgreementUpdate, current_user: dict) -> dict:
        # fetch
        agreement = self.repo.get(agreement_id)
        if not agreement:
            raise HTTPException(status_code=404, detail="Agreement not found")
        # Only freelancer who created it can update and only when DRAFT or REJECTED
        if current_user.get("role") != "FL" or current_user.get("user_id") != agreement["freelancer_id"]:
            raise HTTPException(status_code=403, detail="Not allowed to update")
        if agreement["status"] not in (AgreementStatus.DRAFT.value, AgreementStatus.REJECTED.value, AgreementStatus.REOPENED.value):
            raise HTTPException(status_code=400, detail="Cannot modify agreement in current status")

        update_data = update.model_dump(exclude_unset=True)
        # If milestones changed update total_amount
        if "milestones" in update_data:
            update_data["total_amount"] = self._compute_total(update_data.get("milestones", []))
        updated = self.repo.update(agreement_id, update_data)
        # add timeline entry
        entry = TimelineEntry(action=TimelineAction.UPDATED, user_id=current_user["user_id"], user_role=current_user["role"], note="Agreement updated").model_dump()
        self.repo.add_timeline(agreement_id, entry)
        return updated

    def send_to_client(self, agreement_id: str, current_user: dict) -> dict:
        agreement = self.repo.get(agreement_id)
        if not agreement:
            raise HTTPException(status_code=404, detail="Agreement not found")
        # Only freelancer who created it can send
        if current_user.get("role") != "FL" or current_user.get("user_id") != agreement["freelancer_id"]:
            raise HTTPException(status_code=403, detail="Not allowed")
        if agreement["status"] not in (AgreementStatus.DRAFT.value, AgreementStatus.REOPENED.value, AgreementStatus.REJECTED.value):
            raise HTTPException(status_code=400, detail="Only draft/reopened/rejected agreements can be sent")

        # change status to SENT
        updated = self.repo.change_status(agreement_id, AgreementStatus.SENT.value)
        entry = TimelineEntry(action=TimelineAction.SENT, user_id=current_user["user_id"], user_role=current_user["role"], note="Sent to client").model_dump()
        self.repo.add_timeline(agreement_id, entry)
        return updated

    def client_accept(self, agreement_id: str, sign: AgreementSign, current_user: dict) -> dict:
        agreement = self.repo.get(agreement_id)
        if not agreement:
            raise HTTPException(status_code=404, detail="Agreement not found")
        # Only client can accept and must be the target client
        if current_user.get("role") != "CL" or current_user.get("user_id") != agreement["client_id"]:
            raise HTTPException(status_code=403, detail="Not allowed")
        if agreement["status"] != AgreementStatus.SENT.value:
            raise HTTPException(status_code=400, detail="Only sent agreements can be accepted")

        # attach signature
        sig = sign.model_dump()
        # set client_signature and change status -> ACCEPTED
        updated = self.repo.update(agreement_id, {"client_signature": sig, "status": AgreementStatus.ACCEPTED.value})
        entry = TimelineEntry(action=TimelineAction.ACCEPTED, user_id=current_user["user_id"], user_role=current_user["role"], note="Client accepted and signed").model_dump()
        self.repo.add_timeline(agreement_id, entry)
        return updated

    def client_reject(self, agreement_id: str, reason: str, current_user: dict) -> dict:
        agreement = self.repo.get(agreement_id)
        if not agreement:
            raise HTTPException(status_code=404, detail="Agreement not found")
        if current_user.get("role") != "CL" or current_user.get("user_id") != agreement["client_id"]:
            raise HTTPException(status_code=403, detail="Not allowed")
        if agreement["status"] != AgreementStatus.SENT.value:
            raise HTTPException(status_code=400, detail="Only sent agreements can be rejected")

        updated = self.repo.update(agreement_id, {"status": AgreementStatus.REJECTED.value})
        entry = TimelineEntry(action=TimelineAction.REJECTED, user_id=current_user["user_id"], user_role=current_user["role"], note=reason).model_dump()
        self.repo.add_timeline(agreement_id, entry)
        return updated

    def list_for_freelancer(self, freelancer_id: str, current_user: dict, limit: int = 50, skip: int = 0):
        # Freelancer sees only their agreements; SA can see all
        if current_user.get("role") not in ("FL", "SA") or (current_user.get("role") == "FL" and current_user.get("user_id") != freelancer_id):
            raise HTTPException(status_code=403, detail="Not authorized")
        return self.repo.list_by_freelancer(freelancer_id, limit, skip)

    def list_for_client(self, client_id: str, current_user: dict, limit: int = 50, skip: int = 0):
        if current_user.get("role") not in ("CL", "SA") or (current_user.get("role") == "CL" and current_user.get("user_id") != client_id):
            raise HTTPException(status_code=403, detail="Not authorized")
        return self.repo.list_by_client(client_id, limit, skip)

    def get_agreement(self, agreement_id: str, current_user: dict) -> dict:
        ag = self.repo.get(agreement_id)
        if not ag:
            raise HTTPException(status_code=404, detail="Agreement not found")
        role = current_user.get("role")
        uid = current_user.get("user_id")
        if role == "SA":
            return ag
        # Freelancer can see if owner
        if role == "FL" and ag["freelancer_id"] == uid:
            return ag
        # Client can see if owner
        if role == "CL" and ag["client_id"] == uid:
            return ag
        raise HTTPException(status_code=403, detail="Not authorized")
