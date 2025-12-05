# agreements/service.py
from typing import Dict, Any, List, Optional
from app.models.agreements import AgreementCreate, AgreementInDB, AgreementStatus, SignatureRecord, AgreementFilter
from app.repositories.agreements import AgreementRepository
from app.services.milestones import MilestoneService
from app.services.project import ProjectService
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
        self.project_service = ProjectService()

    def _calc_duration_days(self, start_date: int, end_date: int) -> int:
        """
        Calculate duration in days given start and end epoch timestamps (UTC).
        """
        seconds_in_day = 86400
        return int((end_date - start_date) / seconds_in_day) + 1

    def _calc_total_from_milestones(self, agreement_id: str) -> float:
        """
        Calculate total_amount from sum of all milestone payment amounts.
        """
        milestones = self.milestone_service.list_for_agreement(agreement_id)
        if not milestones:
            return 0.0
        total = sum(m.get("payment", {}).get("amount", 0.0) for m in milestones)
        return float(total)

    def _calc_rate_from_total(self, total_amount: float, duration_days: int) -> float:
        """
        Calculate rate from total_amount / duration_days.
        Returns 0.0 if duration_days is 0 to avoid division by zero.
        """
        if duration_days <= 0:
            return 0.0
        return total_amount / duration_days

    def create_agreement(self, payload: AgreementCreate, created_by: str) -> Dict[str, Any]:
        try:
            duration_days = self._calc_duration_days(payload.start_date, payload.end_date)
            project_check = self.project_service.get(payload.project_id)
            if not project_check:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Project not found")

            # Calculate initial total_amount from milestones if provided, otherwise 0
            initial_total = 0.0
            if payload.milestones:
                initial_total = sum(m.get("payment", {}).get("amount", 0.0) for m in payload.milestones)
            
            # Calculate rate from total_amount / duration_days
            rate = self._calc_rate_from_total(initial_total, duration_days)

            # Calculate platform fee (5%) and freelancer net amount
            platform_fee_rate = 0.05
            platform_fee_amount = initial_total * platform_fee_rate
            freelancer_net_amount = initial_total - platform_fee_amount

            doc = AgreementInDB(
                title=payload.title,
                description=payload.description,
                project_id=payload.project_id,
                client=payload.client,
                freelancer=payload.freelancer,
                rate=rate,
                rate_unit=payload.rate_unit or "day",
                currency=payload.currency or "INR",
                start_date=payload.start_date,
                end_date=payload.end_date,
                project_scope=payload.project_scope,
                additional_terms=payload.additional_terms,
                total_amount=initial_total,
                platform_fee_rate=platform_fee_rate,
                platform_fee_amount=platform_fee_amount,
                freelancer_net_amount=freelancer_net_amount,
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

                # refresh computed fields (total_amount and rate will be recalculated from milestones)
                created = self.repo.get_by_id(created["agreement_id"])
                # Recalculate total_amount and rate from actual milestones
                total_amount = self._calc_total_from_milestones(created["agreement_id"])
                rate = self._calc_rate_from_total(total_amount, duration_days)
                # Recalculate platform fee and freelancer net amount based on updated total_amount
                platform_fee_rate = 0.05
                platform_fee_amount = total_amount * platform_fee_rate
                freelancer_net_amount = total_amount - platform_fee_amount

                self.repo.update(created["agreement_id"], {
                    "total_amount": total_amount,
                    "rate": rate,
                    "num_milestones": len(payload.milestones),
                    "platform_fee_rate": platform_fee_rate,
                    "platform_fee_amount": platform_fee_amount,
                    "freelancer_net_amount": freelancer_net_amount,
                })
                created = self.repo.get_by_id(created["agreement_id"])

            # Send notification to the recipient (if client created, notify freelancer; if freelancer created, notify client)
            try:
                from app.services.notification import NotificationService
                from app.repositories.user import UserRepository
                notification_service = NotificationService()
                user_repo = UserRepository()
                
                # Determine recipient and creator info
                client_id = payload.client.user_id
                freelancer_id = payload.freelancer.user_id
                
                # Determine who created the agreement and who should receive notification
                if created_by == client_id:
                    # Client created, notify freelancer
                    recipient_id = freelancer_id
                    creator_ref = payload.client
                elif created_by == freelancer_id:
                    # Freelancer created, notify client
                    recipient_id = client_id
                    creator_ref = payload.freelancer
                else:
                    # Admin or other role created - notify freelancer by default
                    recipient_id = freelancer_id
                    creator_ref = None  # Will fetch from user repo
                
                # Get creator name from UserRef or fetch from user repo
                if creator_ref:
                    creator_name = creator_ref.name
                    if not creator_name:
                        creator_user = user_repo.get_user_by_id(created_by)
                        if creator_user:
                            creator_name = f"{creator_user.get('first_name', '')} {creator_user.get('last_name', '')}".strip() or creator_user.get('username', 'User')
                        else:
                            creator_name = creator_ref.email or "User"
                else:
                    # Admin case - fetch from user repo
                    creator_user = user_repo.get_user_by_id(created_by)
                    if creator_user:
                        creator_name = f"{creator_user.get('first_name', '')} {creator_user.get('last_name', '')}".strip() or creator_user.get('username', 'Admin')
                    else:
                        creator_name = "Admin"
                
                notification_service.notify_agreement_created(
                    recipient_id=recipient_id,
                    creator_name=creator_name,
                    agreement_title=payload.title,
                    agreement_id=created["agreement_id"],
                    project_id=payload.project_id
                )
                logger.info("Notification sent to recipient: %s for agreement: %s", recipient_id, created["agreement_id"])
            except Exception as e:
                logger.warning("Failed to send agreement creation notification (agreement still created): %s", e)
                # Don't fail the agreement creation if notification fails

            return created
        except PyMongoError:
            logger.exception("DB error creating agreement")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "DB error")

    def get_agreement(self, agreement_id: str) -> Dict[str, Any]:
        ag = self.repo.get_by_id(agreement_id)
        if not ag:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Agreement not found")
        return ag
    
    def get_agreement_filtered(self, filter: AgreementFilter) -> List[Dict[str, Any]]:
        print("Filtering agreements with:", filter.client_id)
        # Convert AgreementFilter → Mongo query
        q = {}

        if filter.status:
            q["status"] = filter.status
        if filter.project_id:
            q["project_id"] = filter.project_id
        if filter.client_id:
            q["client.user_id"] = filter.client_id   # ✅ nested
        if filter.freelancer_id:
            q["freelancer.user_id"] = filter.freelancer_id  # ✅ nested
        if filter.draft is not None:
            q["draft"] = filter.draft
        if filter.active is not None:
            q["status"] = "ACTIVE" if filter.active else {"$ne": "ACTIVE"}
        return self.repo.get_filtered(q)

    def sign_agreement(self, agreement_id: str, user: Dict[str, Any], signature_payload: Dict[str, Any]) -> Dict[str, Any]:
        ag = self.repo.get_by_id(agreement_id)
        if not ag:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Agreement not found")

        if user["user_id"] not in [ag["client"]["user_id"], ag["freelancer"]["user_id"]]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized to sign")

        # Store previous signing state to detect if this is a new signature
        old_client_signed = ag.get("client_signed", False)
        old_freelancer_signed = ag.get("freelancer_signed", False)

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
        
        # Send notification to the other party if they haven't signed yet
        # Only send if this is a new signature (wasn't signed before)
        try:
            from app.services.notification import NotificationService
            notification_service = NotificationService()
            
            client_id = ag["client"]["user_id"]
            freelancer_id = ag["freelancer"]["user_id"]
            agreement_title = ag.get("title", "Agreement")
            project_id = ag.get("project_id")
            
            # Check if freelancer just signed (was false, now true) and client hasn't signed
            if not old_freelancer_signed and update["freelancer_signed"] and not update["client_signed"]:
                freelancer_name = ag["freelancer"].get("name", "Freelancer")
                notification_service.notify_agreement_sign_reminder(
                    recipient_id=client_id,
                    agreement_title=agreement_title,
                    agreement_id=agreement_id,
                    project_id=project_id,
                    other_party_name=freelancer_name
                )
                logger.info("Sign reminder notification sent to client: %s for agreement: %s", client_id, agreement_id)
            
            # Check if client just signed (was false, now true) and freelancer hasn't signed
            elif not old_client_signed and update["client_signed"] and not update["freelancer_signed"]:
                client_name = ag["client"].get("name", "Client")
                notification_service.notify_agreement_sign_reminder(
                    recipient_id=freelancer_id,
                    agreement_title=agreement_title,
                    agreement_id=agreement_id,
                    project_id=project_id,
                    other_party_name=client_name
                )
                logger.info("Sign reminder notification sent to freelancer: %s for agreement: %s", freelancer_id, agreement_id)
        except Exception as e:
            logger.warning("Failed to send agreement sign reminder notification (agreement still signed): %s", e)
            # Continue even if notification fails - agreement is already signed
        
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

        # Remove rate from update_payload if present (rate is calculated, not directly editable)
        if "rate" in update_payload:
            del update_payload["rate"]

        # recompute duration_days and derived fields if dates changed
        recalc = False
        if "start_date" in update_payload or "end_date" in update_payload:
            recalc = True

        if recalc:
            start = update_payload.get("start_date", ag["start_date"])
            end = update_payload.get("end_date", ag["end_date"])
            duration_days = self._calc_duration_days(start, end)
            update_payload["duration_days"] = duration_days
            
            # Recalculate total_amount from milestones and rate from total_amount/duration_days
            total_amount = self._calc_total_from_milestones(agreement_id)
            rate = self._calc_rate_from_total(total_amount, duration_days)

            # Recalculate platform fee and freelancer net amount
            platform_fee_rate = ag.get("platform_fee_rate", 0.05)
            platform_fee_amount = total_amount * platform_fee_rate
            freelancer_net_amount = total_amount - platform_fee_amount

            update_payload["total_amount"] = total_amount
            update_payload["rate"] = rate
            update_payload["platform_fee_rate"] = platform_fee_rate
            update_payload["platform_fee_amount"] = platform_fee_amount
            update_payload["freelancer_net_amount"] = freelancer_net_amount

        updated = self.repo.update(agreement_id, update_payload)
        return updated

    def cancel_agreement(self, agreement_id: str, user: Dict[str, Any], reason: Optional[str] = None):
        ag = self.repo.get_by_id(agreement_id)
        if not ag:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Agreement not found")
        if user["user_id"] not in [ag["client"]["user_id"], ag["freelancer"]["user_id"]] and user.get("role") != "admin":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized")
        return self.repo.update(agreement_id, {"status": AgreementStatus.CANCELLED, "cancelled_reason": reason})

    def pause_agreement(self, agreement_id: str, user: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pause an agreement. Only super admin can pause, and only non-completed agreements can be paused.
        Stores the previous status so it can be restored when unpausing.
        """
        ag = self.repo.get_by_id(agreement_id)
        if not ag:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Agreement not found")
        
        # Only super admin (SA) can pause
        if user.get("role") != "SA":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only super admin can pause agreements")
        
        # Cannot pause completed agreements
        if ag["status"] == AgreementStatus.COMPLETED:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot pause completed agreement")
        
        # Cannot pause already paused agreements
        if ag["status"] == AgreementStatus.PAUSED:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Agreement is already paused")
        
        # Store the current status before pausing, so we can restore it later
        current_status = ag["status"]
        update_data = {
            "status": AgreementStatus.PAUSED,
            "paused_from_status": current_status
        }
        
        updated = self.repo.update(agreement_id, update_data)
        logger.info(f"Agreement {agreement_id} paused from {current_status} by super admin {user.get('user_id')}")
        return updated

    def unpause_agreement(self, agreement_id: str, user: Dict[str, Any]) -> Dict[str, Any]:
        """
        Unpause an agreement. Only super admin can unpause, and only paused agreements can be unpaused.
        Restores the previous status that was stored when pausing.
        """
        ag = self.repo.get_by_id(agreement_id)
        if not ag:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Agreement not found")
        
        # Only super admin (SA) can unpause
        if user.get("role") != "SA":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only super admin can unpause agreements")
        
        # Cannot unpause completed agreements
        if ag["status"] == AgreementStatus.COMPLETED:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot unpause completed agreement")
        
        # Can only unpause paused agreements
        if ag["status"] != AgreementStatus.PAUSED:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Cannot unpause agreement with status {ag['status']}. Only paused agreements can be unpaused.")
        
        # Restore the previous status, or default to ACTIVE if not stored (backward compatibility)
        previous_status = ag.get("paused_from_status")
        if not previous_status:
            # For backward compatibility, if paused_from_status is not set, default to ACTIVE
            previous_status = AgreementStatus.ACTIVE.value
            logger.warning(f"Agreement {agreement_id} does not have paused_from_status, defaulting to ACTIVE")
        
        update_data = {
            "status": previous_status,
            "paused_from_status": None  # Clear the stored status
        }
        
        updated = self.repo.update(agreement_id, update_data)
        logger.info(f"Agreement {agreement_id} unpaused to {previous_status} by super admin {user.get('user_id')}")
        return updated