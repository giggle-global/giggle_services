# milestones/service.py
from typing import Dict, Any, List
from app.models.milestones import MilestoneCreate, MilestoneInDB, MilestoneUpdate, MilestoneStatus
from app.repositories.milestones import MilestoneRepository
from app.repositories.agreements import AgreementRepository
from app.repositories.review import ReviewRepository
from app.repositories.project import ProjectRepository
from app.repositories.portfolio import PortfolioRepository
from app.services.notification import NotificationService
from app.models.notification import NotificationType
from fastapi import HTTPException, status
from pymongo.errors import PyMongoError
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)

class MilestoneService:
    def __init__(self):
        self.milestone_repo = MilestoneRepository()
        self.agreement_repo = AgreementRepository()
        self.review_repo = ReviewRepository()
        self.notification_service = NotificationService()
        self.project_repo = ProjectRepository()
        self.portfolio_repo = PortfolioRepository()

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
        # update agreement's milestone list and recalc totals
        self.agreement_repo.add_milestone(agreement_id, created.get("milestone_id"))

        milestones = self.milestone_repo.list_for_agreement(agreement_id)
        # Calculate total_amount from sum of milestone payments
        total_amount = sum(m.get("payment", {}).get("amount", 0.0) for m in milestones)
        
        # Get agreement to calculate rate
        ag = self.agreement_repo.get_by_id(agreement_id)
        duration_days = ag.get("duration_days", 0)
        if duration_days <= 0:
            # Calculate duration_days if not set
            start_date = ag.get("start_date", 0)
            end_date = ag.get("end_date", 0)
            if start_date > 0 and end_date > 0:
                seconds_in_day = 86400
                duration_days = int((end_date - start_date) / seconds_in_day) + 1
        
        # Calculate rate from total_amount / duration_days
        rate = (total_amount / duration_days) if duration_days > 0 else 0.0
        
        self.agreement_repo.update(agreement_id, {
            "num_milestones": len(milestones),
            "total_amount": total_amount,
            "rate": rate
        })

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

        # Check if agreement is paused - block milestone updates
        if ag.get("status") == "Paused":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot update milestone. This agreement is currently paused.")

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
        # Calculate total_amount from sum of milestone payments
        total_amount = sum(m.get("payment", {}).get("amount", 0.0) for m in milestones)
        
        # Get agreement to calculate rate
        ag = self.agreement_repo.get_by_id(ms["agreement_id"])
        duration_days = ag.get("duration_days", 0)
        if duration_days <= 0:
            # Calculate duration_days if not set
            start_date = ag.get("start_date", 0)
            end_date = ag.get("end_date", 0)
            if start_date > 0 and end_date > 0:
                seconds_in_day = 86400
                duration_days = int((end_date - start_date) / seconds_in_day) + 1
        
        # Calculate rate from total_amount / duration_days
        rate = (total_amount / duration_days) if duration_days > 0 else 0.0
        
        self.agreement_repo.update(ms["agreement_id"], {
            "num_milestones": len(milestones),
            "total_amount": total_amount,
            "rate": rate
        })

        # if all milestones completed with payment received -> check for review before setting agreement Completed
        def _is_fully_completed(m):
            """Check if milestone is completed with payment received"""
            s = m.get("status")
            is_completed_status = (s == MilestoneStatus.COMPLETED or str(s) == str(MilestoneStatus.COMPLETED))
            has_payment_received = m.get("payment_received", False)
            return is_completed_status and has_payment_received

        all_fully_completed = True if len(milestones) > 0 and all(_is_fully_completed(m) for m in milestones) else False
        if all_fully_completed:
            # Check if client has given review for this agreement
            agreement = self.agreement_repo.get_by_id(ms["agreement_id"])
            if agreement:
                client_id = agreement.get("client", {}).get("user_id")
                freelancer_id = agreement.get("freelancer", {}).get("user_id")
                agreement_id = ms["agreement_id"]
                
                has_review = self.review_repo.has_review_for_agreement(agreement_id, client_id, freelancer_id)
                
                if has_review:
                    # Client has given review, mark agreement as Completed
                    self.agreement_repo.update(ms["agreement_id"], {"status": "Completed"})

                    # Also auto-create/update freelancer portfolio entry for this project
                    try:
                        project_id = agreement.get("project_id")
                        freelancer_id = freelancer_id
                        project = None
                        project_name = None
                        if project_id:
                            try:
                                project = self.project_repo.find_by_id(project_id)
                                if project:
                                    project_name = project.get("title") or project.get("project_title")
                            except Exception:
                                project = None
                                project_name = None

                        if freelancer_id and project_id and project:
                            description = (
                                project.get("scope_summary")
                                or project.get("description")
                                or ""
                            )
                            technologies = project.get("key_features") or []
                            cover_image = project.get("cover_image")

                            portfolio_payload = {
                                "title": project_name or "Project",
                                "description": description,
                                "technologies": technologies,
                                "github_link": None,
                                "portfolio_link": None,
                                "cover_image": cover_image,
                            }

                            self.portfolio_repo.upsert_auto_project_from_source(
                                user_id=freelancer_id,
                                source_project_id=project_id,
                                base_payload=portfolio_payload,
                            )
                    except Exception as portfolio_err:
                        logger.warning(
                            "Failed to upsert portfolio entry from milestones for agreement %s: %s",
                            agreement_id,
                            portfolio_err,
                        )
                else:
                    # Client hasn't given review yet, send notifications
                    try:
                        # Notify client: Agreement has been done and need the review
                        self.notification_service.create_notification(
                            user_id=client_id,
                            notification_type=NotificationType.AGREEMENT_UPDATED,
                            title="Review Required",
                            message="Agreement has been done and need the review",
                            data={"agreement_id": agreement_id, "type": "review_required"},
                            # Client messages page with agreement context
                            link=f"/client/gig?agreement_id={agreement_id}"
                        )
                        # Notify freelancer: Agreement has been done
                        self.notification_service.create_notification(
                            user_id=freelancer_id,
                            notification_type=NotificationType.AGREEMENT_UPDATED,
                            title="Agreement Completed",
                            message="Agreement has been done",
                            data={"agreement_id": agreement_id, "type": "agreement_done"},
                            # Freelancer messages page with agreement context
                            link=f"/freelancer/gig?agreement_id={agreement_id}"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send notifications for agreement {agreement_id}: {e}")

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
            # Calculate total_amount from sum of milestone payments
            total_amount = sum(m.get("payment", {}).get("amount", 0.0) for m in milestones)
            
            # Get duration_days from agreement
            duration_days = ag.get("duration_days", 0)
            if duration_days <= 0:
                # Calculate duration_days if not set
                start_date = ag.get("start_date", 0)
                end_date = ag.get("end_date", 0)
                if start_date > 0 and end_date > 0:
                    seconds_in_day = 86400
                    duration_days = int((end_date - start_date) / seconds_in_day) + 1
            
            # Calculate rate from total_amount / duration_days
            rate = (total_amount / duration_days) if duration_days > 0 else 0.0
            
            self.agreement_repo.update(ag["agreement_id"], {
                "num_milestones": len(milestones),
                "total_amount": total_amount,
                "rate": rate
            })
        return {"deleted": deleted}

    def verify_milestone(self, milestone_id: str, user: Dict[str, Any]) -> Dict[str, Any]:
        """
        Client verifies the milestone after freelancer has completed it.
        This enables the "Payment Sent" button for the client.
        """
        ms = self.milestone_repo.get_by_id(milestone_id)
        if not ms:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Milestone not found")

        ag = self.agreement_repo.get_by_id(ms["agreement_id"])
        if not ag:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Agreement not found")

        # Check if both parties have signed the agreement
        if not (ag.get("client_signed", False) and ag.get("freelancer_signed", False)):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Both parties must sign the agreement before milestones can be verified")

        # Only client can verify milestone
        if user["user_id"] != ag["client"]["user_id"] and user.get("role") != "admin":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only client can verify milestone")

        # Check if agreement is paused
        if ag.get("status") == "Paused":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot verify milestone. This agreement is currently paused.")

        # Check if freelancer has completed the milestone
        if not ms.get("freelancer_completed", False):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Freelancer must complete milestone before client can verify it")

        # Check if milestone is already verified
        if ms.get("client_verified", False):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Milestone already verified")

        # Update milestone with verification
        update_data = {
            "client_verified": True,
            "verified_by": user["user_id"],
            "verified_at": self._to_epoch(datetime.utcnow()),
            "status": MilestoneStatus.APPROVED,
            "approved_by": user["user_id"],
            "approved_at": self._to_epoch(datetime.utcnow()),
            "progress": 100,
            "completed_date": self._to_epoch(datetime.utcnow())
        }

        updated_ok = self.milestone_repo.update(milestone_id, update_data)
        if not updated_ok:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to verify milestone")

        # Notify client to send payment after verification
        try:
            payment_info = ms.get("payment", {}) if isinstance(ms, dict) else {}
            amount = payment_info.get("amount")
            currency = payment_info.get("currency")
            self.notification_service.notify_milestone_payment_reminder(
                client_id=ag["client"]["user_id"],
                milestone_title=ms.get("title", "Milestone"),
                milestone_id=milestone_id,
                agreement_id=ms["agreement_id"],
                project_title=ag.get("title"),
                amount=amount,
                currency=currency,
            )
        except Exception as notify_err:
            logger.warning("Failed to send payment reminder notification for milestone %s: %s", milestone_id, notify_err)

        return self.milestone_repo.get_by_id(milestone_id)

    def complete_milestone(self, milestone_id: str, user: Dict[str, Any]) -> Dict[str, Any]:
        """
        Freelancer completes the milestone work.
        This enables the client's "Verify" button.
        """
        ms = self.milestone_repo.get_by_id(milestone_id)
        if not ms:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Milestone not found")

        ag = self.agreement_repo.get_by_id(ms["agreement_id"])
        if not ag:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Agreement not found")

        # Check if both parties have signed the agreement
        if not (ag.get("client_signed", False) and ag.get("freelancer_signed", False)):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Both parties must sign the agreement before milestones can be completed")

        # Only freelancer can complete milestone
        if user["user_id"] != ag["freelancer"]["user_id"] and user.get("role") != "admin":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only freelancer can complete milestone")

        # Check if agreement is paused
        if ag.get("status") == "Paused":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot complete milestone. This agreement is currently paused.")

        # Check if already completed
        if ms.get("freelancer_completed", False):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Milestone already completed")

        # Update milestone with completion
        update_data = {
            "freelancer_completed": True,
            "completed_at": self._to_epoch(datetime.utcnow())
        }

        updated_ok = self.milestone_repo.update(milestone_id, update_data)
        if not updated_ok:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to complete milestone")

        return self.milestone_repo.get_by_id(milestone_id)

    def send_payment(self, milestone_id: str, user: Dict[str, Any]) -> Dict[str, Any]:
        """
        Client confirms that payment has been sent.
        This enables the freelancer's "Received Payment" button.
        """
        ms = self.milestone_repo.get_by_id(milestone_id)
        if not ms:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Milestone not found")

        ag = self.agreement_repo.get_by_id(ms["agreement_id"])
        if not ag:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Agreement not found")

        # Only client can send payment
        if user["user_id"] != ag["client"]["user_id"] and user.get("role") != "admin":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only client can confirm payment sent")

        # Check if agreement is paused
        if ag.get("status") == "Paused":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot send payment. This agreement is currently paused.")

        # Check if milestone is verified by client
        if not ms.get("client_verified", False):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Milestone must be verified before payment can be sent")

        # Check if payment already sent
        if ms.get("payment_sent", False):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Payment already marked as sent")

        # Update milestone with payment sent
        update_data = {
            "payment_sent": True,
            "payment_sent_at": self._to_epoch(datetime.utcnow())
        }

        updated_ok = self.milestone_repo.update(milestone_id, update_data)
        if not updated_ok:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to mark payment as sent")

        # Notify freelancer that client marked payment as sent
        try:
            payment_info = ms.get("payment", {}) if isinstance(ms, dict) else {}
            amount = payment_info.get("amount")
            currency = payment_info.get("currency")
            self.notification_service.notify_milestone_payment_confirmed(
                freelancer_id=ag["freelancer"]["user_id"],
                milestone_title=ms.get("title", "Milestone"),
                milestone_id=milestone_id,
                agreement_id=ms["agreement_id"],
                project_title=ag.get("title"),
                amount=amount,
                currency=currency,
            )
        except Exception as notify_err:
            logger.warning("Failed to send payment confirmation notification for milestone %s: %s", milestone_id, notify_err)

        return self.milestone_repo.get_by_id(milestone_id)

    def receive_payment(self, milestone_id: str, user: Dict[str, Any]) -> Dict[str, Any]:
        """
        Freelancer confirms that payment has been received.
        This completes the milestone and moves to the next milestone if available.
        """
        ms = self.milestone_repo.get_by_id(milestone_id)
        if not ms:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Milestone not found")

        ag = self.agreement_repo.get_by_id(ms["agreement_id"])
        if not ag:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Agreement not found")

        # Only freelancer can receive payment
        if user["user_id"] != ag["freelancer"]["user_id"] and user.get("role") != "admin":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only freelancer can confirm payment received")

        # Check if agreement is paused
        if ag.get("status") == "Paused":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot receive payment. This agreement is currently paused.")

        # Check if payment was sent by client
        if not ms.get("payment_sent", False):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Client must send payment before freelancer can receive it")

        # Check if payment already received
        if ms.get("payment_received", False):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Payment already marked as received")

        # Update milestone with payment received
        update_data = {
            "payment_received": True,
            "payment_received_at": self._to_epoch(datetime.utcnow()),
            "status": MilestoneStatus.COMPLETED
        }

        updated_ok = self.milestone_repo.update(milestone_id, update_data)
        if not updated_ok:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to mark payment as received")

        # Update payment in payment breakdown
        payment_data = ms.get("payment", {})
        if payment_data:
            payment_data["payment_released"] = True
            self.milestone_repo.update(milestone_id, {"payment": payment_data})

        # Move to next milestone if available
        milestones = self.milestone_repo.list_for_agreement(ms["agreement_id"])
        current_index = next((i for i, m in enumerate(milestones) if m["milestone_id"] == milestone_id), -1)
        
        if current_index >= 0 and current_index < len(milestones) - 1:
            next_milestone = milestones[current_index + 1]
            if next_milestone.get("status") == MilestoneStatus.PENDING:
                # Set next milestone to InProgress
                self.milestone_repo.update(next_milestone["milestone_id"], {
                    "status": MilestoneStatus.IN_PROGRESS,
                    "start_date": self._to_epoch(datetime.utcnow())
                })

        # Check if all milestones are completed and payment received -> check for review before setting agreement Completed
        # Refresh milestones list to get the updated status
        milestones = self.milestone_repo.list_for_agreement(ms["agreement_id"])
        def _is_fully_completed(m):
            """Check if milestone is completed with payment received"""
            s = m.get("status")
            is_completed_status = (s == MilestoneStatus.COMPLETED or str(s) == str(MilestoneStatus.COMPLETED))
            has_payment_received = m.get("payment_received", False)
            return is_completed_status and has_payment_received

        all_fully_completed = True if len(milestones) > 0 and all(_is_fully_completed(m) for m in milestones) else False
        if all_fully_completed:
            # Check if client has given review for this agreement
            agreement = self.agreement_repo.get_by_id(ms["agreement_id"])
            if agreement:
                client_id = agreement.get("client", {}).get("user_id")
                freelancer_id = agreement.get("freelancer", {}).get("user_id")
                agreement_id = ms["agreement_id"]
                
                has_review = self.review_repo.has_review_for_agreement(agreement_id, client_id, freelancer_id)
                
                if has_review:
                    # Client has given review, mark agreement as Completed
                    self.agreement_repo.update(ms["agreement_id"], {"status": "Completed"})
                else:
                    # Client hasn't given review yet, send notifications
                    try:
                        # Notify client: Agreement has been done and need the review
                        self.notification_service.create_notification(
                            user_id=client_id,
                            notification_type=NotificationType.AGREEMENT_UPDATED,
                            title="Review Required",
                            message="Agreement has been done and need the review",
                            data={"agreement_id": agreement_id, "type": "review_required"},
                            link=f"/client/milestone?agreement_id={agreement_id}"
                        )
                        # Notify freelancer: Agreement has been done
                        self.notification_service.create_notification(
                            user_id=freelancer_id,
                            notification_type=NotificationType.AGREEMENT_UPDATED,
                            title="Agreement Completed",
                            message="Agreement has been done",
                            data={"agreement_id": agreement_id, "type": "agreement_done"},
                            link=f"/freelancer/gig?agreement_id={agreement_id}"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send notifications for agreement {agreement_id}: {e}")

        return self.milestone_repo.get_by_id(milestone_id)