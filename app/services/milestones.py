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

    @staticmethod
    def _to_epoch(ts: datetime) -> int:
        return int(ts.timestamp())

    def add_milestone(self, agreement_id: str, payload: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        ag = self.agreement_repo.get_by_id(agreement_id)
        if not ag:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Agreement not found")

        if user["user_id"] not in [ag["client"]["user_id"], ag["freelancer"]["user_id"]] and user.get("role") != "admin":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized to add milestone")

        if ag["status"] in ["Cancelled", "Completed"]:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot add milestone to cancelled/completed agreement")

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
        # update agreement's milestone list and recalc totals (num_milestones, total_amount)
        self.agreement_repo.add_milestone(agreement_id, created.get("milestone_id"))

        milestones = self.milestone_repo.list_for_agreement(agreement_id)
        total = sum(m.get("payment", {}).get("amount", 0) for m in milestones)
        self.agreement_repo.update(agreement_id, {"total_amount": total, "num_milestones": len(milestones)})

        return created

    def list_for_agreement(self, agreement_id: str) -> List[Dict[str, Any]]:
        return self.milestone_repo.list_for_agreement(agreement_id)

    def update_milestone(self, milestone_id: str, update_payload: MilestoneUpdate, user: Dict[str, Any]) -> Dict[str, Any]:
        # fetch existing milestone
        ms = self.milestone_repo.get_by_id(milestone_id)
        if not ms:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Milestone not found")

        # fetch agreement to validate roles
        ag = self.agreement_repo.get_by_id(ms["agreement_id"])
        if not ag:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Agreement not found")

        # authorization: only client, freelancer or admin can touch milestone
        if user["user_id"] not in [ag["client"]["user_id"], ag["freelancer"]["user_id"]] and user.get("role") != "SA":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized")

        # Build update dict from pydantic model — only fields provided by client
        update_data: Dict[str, Any] = update_payload.dict(exclude_unset=True)

        # if updating progress -> only freelancer or admin
        if "progress" in update_data:
            if user["user_id"] != ag["freelancer"]["user_id"] and user.get("role") != "admin":
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Only freelancer can update progress")

            try:
                progress_val = int(update_data.get("progress", 0))
            except (TypeError, ValueError):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid progress value")
        else:
            progress_val = None

        # if setting status to APPROVED -> only client or admin
        status_val = update_data.get("status")
        # handle both enum and string comparison
        is_approving = status_val == MilestoneStatus.APPROVED or str(status_val) == str(MilestoneStatus.APPROVED)
        if is_approving:
            if user["user_id"] != ag["client"]["user_id"] and user.get("role") != "admin":
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Only client can approve milestone")

            update_data["approved_by"] = user["user_id"]
            update_data["approved_at"] = self._to_epoch(datetime.utcnow())
            update_data["progress"] = 100
            progress_val = 100
            # TODO: trigger payment release/event here

        # if progress == 100 -> mark completed date and set status COMPLETED
        if progress_val is not None and progress_val >= 100:
            update_data["status"] = MilestoneStatus.COMPLETED
            update_data["completed_date"] = self._to_epoch(datetime.utcnow())

        # defensive: convert datetime to epoch if user inadvertently provided datetimes
        if "approved_at" in update_data and isinstance(update_data["approved_at"], datetime):
            update_data["approved_at"] = self._to_epoch(update_data["approved_at"])
        if "completed_date" in update_data and isinstance(update_data["completed_date"], datetime):
            update_data["completed_date"] = self._to_epoch(update_data["completed_date"])

        # Persist only provided fields. Choose one depending on your repo:
        # Option A: repo.update expects a $set-style pymongo update document:
        # updated_ok = self.milestone_repo.update(milestone_id, {"$set": update_data})
        #
        # Option B: repo.update expects a plain dict and internally does $set:
        updated_ok = self.milestone_repo.update(milestone_id, update_data)

        if not updated_ok:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to update milestone")

        # fetch fresh milestone after update to compute agreement summary
        updated_ms = self.milestone_repo.get_by_id(milestone_id)

        # recompute agreement summary
        milestones = self.milestone_repo.list_for_agreement(ms["agreement_id"]) or []
        total = sum(m.get("payment", {}).get("amount", 0) for m in milestones)
        self.agreement_repo.update(ms["agreement_id"], {"total_amount": total, "num_milestones": len(milestones)})

        # if all milestones approved -> set agreement Completed
        def _is_approved(m):
            s = m.get("status")
            return s == MilestoneStatus.APPROVED or str(s) == str(MilestoneStatus.APPROVED)

        all_approved = True if len(milestones) > 0 and all(_is_approved(m) for m in milestones) else False
        if all_approved:
            self.agreement_repo.update(ms["agreement_id"], {"status": "Completed"})

        return updated_ms

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
