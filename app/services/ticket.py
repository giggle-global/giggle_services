# app/services/ticket.py
import logging
from typing import Any, Dict, Optional, List
from fastapi import HTTPException, status
from pymongo.errors import PyMongoError

from app.repositories.ticket import TicketRepository
from app.services.chat import ChatService
from app.services.request import RequestService
from app.services.notification import NotificationService
from app.services.project import ProjectService
from app.models.ticket import (
    TicketCreate,
    TicketUpdate,
    TicketStatusUpdate,
    TicketOut,
    TimelineEntry,
    TimelineAction,
    TicketStatus,
    TicketAdminResponse,
)

logger = logging.getLogger(__name__)


class TicketService:
    def __init__(self, repo: Optional[TicketRepository] = None):
        self.repo = repo or TicketRepository()
        self.chat_service = ChatService()
        self.request_service = RequestService()
        self.notification_service = NotificationService()
        self.project_service = ProjectService()

    # ---------- Helpers ----------
    def _get_ticket_or_404(self, ticket_id: str) -> Dict[str, Any]:
        if not ticket_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "ticket_id is required")
        try:
            ticket = self.repo.get_ticket(ticket_id)
        except PyMongoError:
            logger.exception("Mongo error fetching ticket: %s", ticket_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to fetch ticket")
        if not ticket:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
        return ticket

    # def _assert_fl(self, user: Dict[str, Any]):
    #     if not user or user.get("role") != "FL":
    #         raise HTTPException(status.HTTP_403_FORBIDDEN, "Only freelancers are allowed")

    def _assert_sa(self, user: Dict[str, Any]):
        if not user or user.get("role") != "SA":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only super admin is allowed")

    # ---------- Create ----------
    def create_ticket(self, freelancer_id: str, client_id: str, subject: str, description: str, user: Dict[str, Any], project_id: Optional[str] = None, agreement_id: Optional[str] = None) -> Dict[str, Any]:
        if not freelancer_id or not client_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "freelancer_id and client_id are required")
        if not subject or not description:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "subject and description are required")
        # if user.get("user_id") != freelancer_id:
        #     raise HTTPException(status.HTTP_403_FORBIDDEN, "Freelancer mismatch")

        timeline = [
            TimelineEntry(
                action=TimelineAction.CREATED,
                user_id=user["user_id"],
                user_role=user["role"],
                comment="Ticket created",
            ).model_dump()
        ]

        data = {
            "freelancer_id": freelancer_id,
            "client_id": client_id,
            "subject": subject,
            "description": description,
            "status": TicketStatus.OPEN.value,   # store primitive value
            "solution": None,
            "timeline": timeline,
        }
        
        # Add optional project_id and agreement_id if provided
        if project_id:
            data["project_id"] = project_id
        if agreement_id:
            data["agreement_id"] = agreement_id

        try:
            created = self.repo.create_ticket(data)
            logger.info("Ticket created: freelancer=%s client=%s", freelancer_id, client_id)
            
            # Note: Dispute creation no longer sends chat messages
            # Instead, a badge is shown in the UI when a dispute exists
            # New: send notification to the opposite party when a dispute is raised
            try:
                raised_by_role = user.get("role", "")
                # Determine recipient: if caller is client, notify freelancer; if caller is freelancer, notify client
                if user.get("user_id") == client_id:
                    recipient_id = freelancer_id
                else:
                    recipient_id = client_id

                # Resolve project name if possible
                project_name = None
                effective_project_id = project_id or created.get("project_id", "")
                if effective_project_id:
                    try:
                        project = self.project_service.get(effective_project_id)
                        project_name = getattr(project, "title", None) or getattr(project, "project_title", None)
                    except Exception:
                        project_name = None

                self.notification_service.notify_dispute_raised(
                    recipient_id=recipient_id,
                    raised_by_role=raised_by_role or "user",
                    subject=subject,
                    project_name=project_name,
                    agreement_id=agreement_id or created.get("agreement_id"),
                    ticket_id=created.get("ticket_id"),
                )
            except Exception as notif_err:
                # Do not fail ticket creation if notification fails
                logger.warning("Failed to send dispute raised notification: %s", notif_err)
            
            return created
        except PyMongoError:
            logger.exception("Mongo error creating ticket: freelancer=%s client=%s", freelancer_id, client_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to create ticket")

    # ---------- Update ----------
    def update_ticket(self, ticket_id: str, update: TicketUpdate, user: Dict[str, Any]) -> Dict[str, Any]:
        ticket = self._get_ticket_or_404(ticket_id)

        if ticket.get("freelancer_id") != user.get("user_id") or ticket.get("status") == TicketStatus.CLOSED.value or ticket.get("client_id") != user.get("user_id"):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the freelancer or client can update their ticket or Already closed ticket cannot be updated")

        update_dict = update.model_dump(exclude_unset=True)
        if not update_dict:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nothing to update")

        try:
            self.repo.update_ticket(ticket_id, update_dict)
            self.repo.add_timeline_entry(
                ticket_id,
                TimelineEntry(
                    action=TimelineAction.UPDATED,
                    user_id=user["user_id"],
                    user_role=user["role"],
                    comment="Ticket updated",
                ).model_dump(),
            )
            updated = self.repo.get_ticket(ticket_id)
            logger.info("Ticket updated: %s", ticket_id)
            return updated
        except PyMongoError:
            logger.exception("Mongo error updating ticket: %s", ticket_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to update ticket")

    # ---------- Status change ----------
    def update_ticket_status(self, ticket_id: str, status_in: TicketStatus, user: Dict[str, Any]) -> Dict[str, Any]:
        ticket = self._get_ticket_or_404(ticket_id)
        current_status = ticket.get("status")

        # Normalize inputs
        if isinstance(status_in, TicketStatus):
            new_status_value = status_in.value
        else:
            new_status_value = str(status_in)

        # Permissions & workflow rules
        role = user.get("role")
        if role == "FL":
            if new_status_value != TicketStatus.REOPENED.value:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Freelancers can only reopen tickets")
            if current_status != TicketStatus.CLOSED.value:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Can only reopen a closed ticket")
        elif role == "SA":
            if new_status_value not in {
                TicketStatus.IN_PROGRESS.value,
                TicketStatus.RESOLVED.value,
                TicketStatus.CLOSED.value,
            }:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid status for admin")
        else:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized")

        if current_status == new_status_value:
            raise HTTPException(status.HTTP_409_CONFLICT, "Ticket already in this status")

        try:
            self.repo.update_ticket(ticket_id, {"status": new_status_value})
            self.repo.add_timeline_entry(
                ticket_id,
                TimelineEntry(
                    action=TimelineAction.STATUS_CHANGED,
                    user_id=user["user_id"],
                    user_role=user["role"],
                    status=new_status_value,
                    comment=f"Status changed to {new_status_value}",
                ).model_dump(),
            )
            updated = self.repo.get_ticket(ticket_id)
            logger.info("Ticket status updated: %s -> %s (ticket=%s)", current_status, new_status_value, ticket_id)

            # When dispute becomes resolved, notify both parties
            if new_status_value == TicketStatus.RESOLVED.value:
                try:
                    client_id = updated.get("client_id")
                    freelancer_id = updated.get("freelancer_id")
                    subject = updated.get("subject", "")
                    proj_id = updated.get("project_id", "")
                    agreement_id = updated.get("agreement_id")

                    # Resolve project name if possible
                    project_name = None
                    if proj_id:
                        try:
                            project = self.project_service.get(proj_id)
                            project_name = getattr(project, "title", None) or getattr(project, "project_title", None)
                        except Exception:
                            project_name = None

                    self.notification_service.notify_dispute_resolved(
                        client_id=client_id,
                        freelancer_id=freelancer_id,
                        subject=subject,
                        project_name=project_name,
                        agreement_id=agreement_id,
                        ticket_id=updated.get("ticket_id"),
                    )
                except Exception as notif_err:
                    logger.warning("Failed to send dispute resolved notifications: %s", notif_err)

            return updated
        except PyMongoError:
            logger.exception("Mongo error changing ticket status: %s", ticket_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to change ticket status")

    # ---------- Admin respond & close ----------
    def admin_respond(self, ticket_id: str, response: TicketAdminResponse, user: Dict[str, Any]) -> Dict[str, Any]:
        self._assert_sa(user)
        ticket = self._get_ticket_or_404(ticket_id)

        comment = (response.comment or "").strip()
        if not comment:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "comment is required")

        try:
            self.repo.update_ticket(ticket_id, {"solution": comment, "status": TicketStatus.CLOSED.value})
            self.repo.add_timeline_entry(
                ticket_id,
                TimelineEntry(
                    action=TimelineAction.ADMIN_COMMENT,
                    user_id=user["user_id"],
                    user_role=user["role"],
                    comment=comment,
                    status=TicketStatus.CLOSED.value,
                ).model_dump(),
            )
            updated = self.repo.get_ticket(ticket_id)
            logger.info("Admin responded and closed ticket: %s", ticket_id)
            return updated
        except PyMongoError:
            logger.exception("Mongo error in admin_respond: %s", ticket_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to respond to ticket")

    # ---------- Read ----------
    def get_ticket(self, ticket_id: str, user: Dict[str, Any]) -> Dict[str, Any]:
        ticket = self._get_ticket_or_404(ticket_id)
        role = user.get("role")
        if role == "FL" and ticket.get("freelancer_id") != user.get("user_id"):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed")
        if role == "SA":
            return ticket
        # (Optional) If clients should see their tickets, add a rule:
        # if role == "CL" and ticket.get("client_id") == user.get("user_id"):
        #     return ticket
        return ticket if role == "FL" else (_ for _ in ()).throw(HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed"))

    def list_tickets(self, user: Dict[str, Any]) -> List[Dict[str, Any]]:
        role = user.get("role")
        user_id = user.get("user_id")
        try:
            if role == "SA":
                items = self.repo.get_all_tickets()
            elif role == "FL":
                if not user_id:
                    raise HTTPException(status.HTTP_400_BAD_REQUEST, "user_id is required")
                items = self.repo.get_tickets_by_freelancer(user_id)
            elif role == "CL":
                if not user_id:
                    raise HTTPException(status.HTTP_400_BAD_REQUEST, "user_id is required")
                items = self.repo.get_tickets_by_client(user_id)
            else:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed")
            
            # Ensure all items are properly formatted (no None values, proper types)
            if items:
                # Filter out any None items and ensure dict format
                items = [item for item in items if item is not None and isinstance(item, dict)]
                # Ensure all required fields are present for TicketOut model
                for item in items:
                    # Ensure required fields have default values if missing
                    if "subject" not in item or item["subject"] is None:
                        item["subject"] = ""
                    if "description" not in item:
                        item["description"] = None
                    if "solution" not in item:
                        item["solution"] = None
                    if "project_id" not in item:
                        item["project_id"] = None
                    if "agreement_id" not in item:
                        item["agreement_id"] = None
                    # Handle timeline - convert datetime objects to ISO strings or None
                    if "timeline" not in item:
                        item["timeline"] = None
                    elif item["timeline"] is not None:
                        # Convert timeline entries to serializable format
                        timeline_list = []
                        for entry in item["timeline"]:
                            if isinstance(entry, dict):
                                timeline_entry = dict(entry)
                                # Convert datetime objects to ISO strings
                                if "timestamp" in timeline_entry and hasattr(timeline_entry["timestamp"], "isoformat"):
                                    timeline_entry["timestamp"] = timeline_entry["timestamp"].isoformat()
                                timeline_list.append(timeline_entry)
                        item["timeline"] = timeline_list if timeline_list else None
                    # Ensure status is a valid string
                    if "status" not in item or not item["status"]:
                        item["status"] = "open"
                    # Remove any MongoDB ObjectId or other non-serializable fields
                    item.pop("_id", None)
            
            logger.debug("Tickets listed: role=%s count=%s", role, len(items) if items else 0)
            return items or []
        except HTTPException:
            raise  # Re-raise HTTP exceptions
        except PyMongoError as e:
            logger.exception("Mongo error listing tickets: role=%s user=%s error=%s", role, user_id, str(e))
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to list tickets")
        except Exception as e:
            logger.exception("Unexpected error listing tickets: role=%s user=%s error=%s", role, user_id, str(e))
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Failed to list tickets: {str(e)}")
    
    def get_tickets_by_project_id(self, project_id: str, user: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get all tickets for a specific project_id"""
        try:
            items = self.repo.get_tickets_by_project_id(project_id)
            logger.debug("Tickets by project_id: project_id=%s count=%s", project_id, len(items) if items else 0)
            return items
        except PyMongoError:
            logger.exception("Mongo error fetching tickets by project_id: project_id=%s", project_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to fetch tickets by project_id")
    
    def has_active_dispute(self, project_id: str) -> bool:
        """Check if there's an active dispute for a project"""
        try:
            return self.repo.has_active_dispute(project_id)
        except PyMongoError:
            logger.exception("Mongo error checking active dispute: project_id=%s", project_id)
            return False
    
    def get_tickets_by_agreement_id(self, agreement_id: str, user: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get all tickets for a specific agreement_id"""
        try:
            items = self.repo.get_tickets_by_agreement_id(agreement_id)
            logger.debug("Tickets by agreement_id: agreement_id=%s count=%s", agreement_id, len(items) if items else 0)
            return items
        except PyMongoError:
            logger.exception("Mongo error fetching tickets by agreement_id: agreement_id=%s", agreement_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to fetch tickets by agreement_id")
    
    def has_active_dispute_by_agreement(self, agreement_id: str) -> bool:
        """Check if there's an active dispute for an agreement"""
        try:
            return self.repo.has_active_dispute_by_agreement(agreement_id)
        except PyMongoError:
            logger.exception("Mongo error checking active dispute: agreement_id=%s", agreement_id)
            return False