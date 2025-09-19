# agreements/service.py
from typing import Dict, Any, List, Optional
from app.models.agreements import AgreementCreate, AgreementInDB, AgreementStatus, SignatureRecord
from app.repositories.agreements import AgreementRepository
from app.services.milestones import MilestoneService
from pymongo.errors import PyMongoError
from fastapi import HTTPException, status
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class AgreementService:
    def __init__(self):
        self.repo = AgreementRepository()
        # optionally used to create initial milestones
        self.milestone_service = MilestoneService()

    def _calc_duration_days(self, start_date, end_date) -> int:
        return (end_date - start_date).days + 1

    def _calc_total_from_rate(self, rate: float, rate_unit: str, duration_days: int) -> float:
        # simple default: rate_unit "day" => rate * duration_days
        # if "week" or "hour" implement accordingly. For now only "day" and "week".
        if rate_unit == "week":
            weeks = max(1, round(duration_days / 7))
            return rate * weeks
        # default day
        return rate * duration_days

    def create_agreement(self, payload: AgreementCreate, created_by: str) -> Dict[str, Any]:
        try:
            duration_days = self._calc_duration_days(payload.start_date, payload.end_date)
            total_amount = self._calc_total_from_rate(payload.rate, payload.rate_unit or "day", duration_days)

            doc = AgreementInDB(
                title=payload.title,
                description=payload.description,
                client=payload.client,
                freelancer=payload.freelancer,
                rate=payload.rate,
                rate_unit=payload.rate_unit or "day",
                currency=payload.currency or "INR",
                start_date=payload.start_date,
                end_date=payload.end_date,
                project_scope=payload.project_scope,
                additional_terms=payload.additional_terms,
                total_amount=total_amount,
                duration_days=duration_days,
                num_milestones=0,
                created_by=created_by,
                draft=True
            ).model_dump()

            created = self.repo.create(doc)

            # optional: create initial milestones (payload.milestones expected list of dicts)
            if payload.milestones and self.milestone_service:
                for m in payload.milestones:
                    self.milestone_service.add_milestone(created["agreement_id"], m, {"user_id": created_by, "role": "client"})

                # refresh computed fields
                created = self.repo.get_by_id(created["agreement_id"])

            return created
        except PyMongoError:
            logger.exception("DB error creating agreement")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "DB error")

    def get_agreement(self, agreement_id: str) -> Dict[str, Any]:
        ag = self.repo.get_by_id(agreement_id)
        if not ag:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Agreement not found")
        return ag

    def sign_agreement(self, agreement_id: str, user: Dict[str, Any], signature_payload: Dict[str, Any]) -> Dict[str, Any]:
        ag = self.repo.get_by_id(agreement_id)
        if not ag:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Agreement not found")

        if user["user_id"] not in [ag["client"]["user_id"], ag["freelancer"]["user_id"]]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized to sign")

        sig = SignatureRecord(
            user_id=user["user_id"],
            name=signature_payload.get("name") or user.get("name"),
            signature_type=signature_payload.get("signature_type") or "text",
            signature_value=signature_payload.get("signature_value")
        ).model_dump()

        signatures = ag.get("signatures", {})
        signatures[user["user_id"]] = sig

        update = {
            "signatures": signatures,
            "client_signed": bool(signatures.get(ag["client"]["user_id"])),
            "freelancer_signed": bool(signatures.get(ag["freelancer"]["user_id"]))
        }

        # if both signed, mark Active and draft->False
        if update["client_signed"] and update["freelancer_signed"]:
            update["status"] = AgreementStatus.ACTIVE
            update["draft"] = False

        updated = self.repo.update(agreement_id, update)
        return updated

    def update_agreement(self, agreement_id: str, update_payload: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        ag = self.repo.get_by_id(agreement_id)
        if not ag:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Agreement not found")
        # only client/freelancer/admin and only when not cancelled/completed
        if user["user_id"] not in [ag["client"]["user_id"], ag["freelancer"]["user_id"]] and user.get("role") != "admin":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized")
        if ag["status"] in [AgreementStatus.CANCELLED, AgreementStatus.COMPLETED]:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot update cancelled/completed agreement")

        # recompute totals if rate or dates changed
        recalc = False
        if "rate" in update_payload or "start_date" in update_payload or "end_date" in update_payload or "rate_unit" in update_payload:
            recalc = True

        if recalc:
            start = update_payload.get("start_date", ag["start_date"])
            end = update_payload.get("end_date", ag["end_date"])
            rate = update_payload.get("rate", ag["rate"])
            rate_unit = update_payload.get("rate_unit", ag.get("rate_unit", "day"))
            duration_days = self._calc_duration_days(start, end)
            update_payload["duration_days"] = duration_days
            update_payload["total_amount"] = self._calc_total_from_rate(rate, rate_unit, duration_days)

        updated = self.repo.update(agreement_id, update_payload)
        return updated

    def cancel_agreement(self, agreement_id: str, user: Dict[str, Any], reason: Optional[str] = None):
        ag = self.repo.get_by_id(agreement_id)
        if not ag:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Agreement not found")
        if user["user_id"] not in [ag["client"]["user_id"], ag["freelancer"]["user_id"]] and user.get("role") != "admin":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized")
        return self.repo.update(agreement_id, {"status": AgreementStatus.CANCELLED, "cancelled_reason": reason})
