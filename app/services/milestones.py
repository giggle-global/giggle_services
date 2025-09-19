# milestones/service.py
from typing import Dict, Any, List
from app.models.milestones import MilestoneCreate, MilestoneInDB, MilestoneUpdate, MilestoneStatus
from app.repositories.milestones import MilestoneRepository
from app.repositories.agreements import AgreementRepository
from fastapi import HTTPException, status
from pymongo.errors import PyMongoError
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)

class MilestoneService:
    def __init__(self):
        self.milestone_repo = MilestoneRepository()
        self.agreement_repo = AgreementRepository()

    def add_milestone(self, agreement_id: str, payload: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        # payload can be dict matching MilestoneCreate
        ag = self.agreement_repo.get_by_id(agreement_id)
        if not ag:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Agreement not found")

        # only client/freelancer/admin can add (client is typical)
        if user["user_id"] not in [ag["client"]["user_id"], ag["freelancer"]["user_id"]] and user.get("role") != "admin":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized to add milestone")

        if ag["status"] in ["Cancelled", "Completed"]:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot add milestone to cancelled/completed agreement")

        # validate payload
        m_payload = MilestoneCreate(**payload) if not isinstance(payload, MilestoneCreate) else payload

        m_doc = MilestoneInDB(
            agreement_id=agreement_id,
            title=m_payload.title,
            description=m_payload.description,
            due_date=m_payload.due_date,
            est_start_date=m_payload.est_start_date,
            payment=m_payload.payment,
            deliverables=m_payload.deliverables or []
        ).model_dump()

        created = self.milestone_repo.create(m_doc)
        print("Created milestone:", created.get("milestone_id"))
        # update agreement's milestone list and recalc totals (num_milestones, total_amount)
        self.agreement_repo.add_milestone(agreement_id, created.get("milestone_id"))

        # recompute agreement summary: sum milestone payments
        milestones = self.milestone_repo.list_for_agreement(agreement_id)
        total = sum(m.get("payment", {}).get("amount", 0) for m in milestones)
        self.agreement_repo.update(agreement_id, {"total_amount": total, "num_milestones": len(milestones)})

        return created

    def list_for_agreement(self, agreement_id: str) -> List[Dict[str, Any]]:
        return self.milestone_repo.list_for_agreement(agreement_id)

    def update_milestone(self, milestone_id: str, update_payload: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        ms = self.milestone_repo.get_by_id(milestone_id)
        if not ms:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Milestone not found")
        ag = self.agreement_repo.get_by_id(ms["agreement_id"])
        if user["user_id"] not in [ag["client"]["user_id"], ag["freelancer"]["user_id"]] and user.get("role") != "admin":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized")

        # if updating progress -> only freelancer or admin
        if "progress" in update_payload and user["user_id"] != ag["freelancer"]["user_id"] and user.get("role") != "admin":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only freelancer can update progress")

        # if setting status to APPROVED -> only client or admin
        if update_payload.get("status") == MilestoneStatus.APPROVED and user["user_id"] != ag["client"]["user_id"] and user.get("role") != "admin":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only client can approve milestone")

        # if approved, set approved_by and approved_at and progress 100
        if update_payload.get("status") == MilestoneStatus.APPROVED:
            update_payload["approved_by"] = user["user_id"]
            update_payload["approved_at"] = datetime.utcnow()
            update_payload["progress"] = 100
            # TODO: trigger payment release call / event here

        # if progress == 100 -> mark completed date
        if "progress" in update_payload and int(update_payload.get("progress", 0)) >= 100:
            update_payload["status"] = MilestoneStatus.COMPLETED
            update_payload["completed_date"] = date.today()

        updated = self.milestone_repo.update(milestone_id, update_payload)

        # after update, if milestone payment changed or milestones changed, update agreement summary
        milestones = self.milestone_repo.list_for_agreement(ms["agreement_id"])
        total = sum(m.get("payment", {}).get("amount", 0) for m in milestones)
        self.agreement_repo.update(ms["agreement_id"], {"total_amount": total, "num_milestones": len(milestones)})

        # if all milestones approved -> set agreement Completed
        ag_after = self.agreement_repo.get_by_id(ms["agreement_id"])
        all_approved = True if len(milestones) > 0 and all(m.get("status") == MilestoneStatus.APPROVED for m in milestones) else False
        if all_approved:
            self.agreement_repo.update(ms["agreement_id"], {"status": "Completed"})

        return updated

    def approve_milestone(self, milestone_id: str, user: Dict[str, Any], approve: bool = True, notes: str = None):
        ms = self.milestone_repo.get_by_id(milestone_id)
        if not ms:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Milestone not found")
        ag = self.agreement_repo.get_by_id(ms["agreement_id"])
        if user["user_id"] != ag["client"]["user_id"] and user.get("role") != "admin":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only client can approve")
        if approve:
            return self.update_milestone(milestone_id, {"status": MilestoneStatus.APPROVED, "approval_notes": notes}, user)
        else:
            return self.update_milestone(milestone_id, {"status": MilestoneStatus.REJECTED, "approval_notes": notes}, user)

    def delete_milestone(self, milestone_id: str, user: Dict[str, Any]):
        ms = self.milestone_repo.get_by_id(milestone_id)
        if not ms:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Milestone not found")
        ag = self.agreement_repo.get_by_id(ms["agreement_id"])
        if user["user_id"] not in [ag["client"]["user_id"], ag["freelancer"]["user_id"]] and user.get("role") != "admin":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized")
        # remove milestone from collection
        deleted = self.milestone_repo.delete(milestone_id)
        if deleted:
            # remove from agreement.milestones and recalc totals
            # use $pull and recompute
            self.agreement_repo.col.update_one({"agreement_id": ag["agreement_id"]}, {"$pull": {"milestones": milestone_id}})
            milestones = self.milestone_repo.list_for_agreement(ag["agreement_id"])
            total = sum(m.get("payment", {}).get("amount", 0) for m in milestones)
            self.agreement_repo.update(ag["agreement_id"], {"total_amount": total, "num_milestones": len(milestones)})
        return {"deleted": deleted}
