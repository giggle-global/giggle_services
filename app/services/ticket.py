# app/services/ticket.py
import logging
from typing import Any, Dict, Optional, List
from fastapi import HTTPException, status
from pymongo.errors import PyMongoError

from app.repositories.ticket import TicketRepository
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

    def _assert_fl(self, user: Dict[str, Any]):
        if not user or user.get("role") != "FL":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only freelancers are allowed")

    def _assert_sa(self, user: Dict[str, Any]):
        if not user or user.get("role") != "SA":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only super admin is allowed")

    # ---------- Create ----------
    def create_ticket(self, freelancer_id: str, client_id: str, subject: str, description: str, user: Dict[str, Any]) -> Dict[str, Any]:
        self._assert_fl(user)
        if not freelancer_id or not client_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "freelancer_id and client_id are required")
        if not subject or not description:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "subject and description are required")
        if user.get("user_id") != freelancer_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Freelancer mismatch")

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

        try:
            created = self.repo.create_ticket(data)
            logger.info("Ticket created: freelancer=%s client=%s", freelancer_id, client_id)
            return created
        except PyMongoError:
            logger.exception("Mongo error creating ticket: freelancer=%s client=%s", freelancer_id, client_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to create ticket")

    # ---------- Update ----------
    def update_ticket(self, ticket_id: str, update: TicketUpdate, user: Dict[str, Any]) -> Dict[str, Any]:
        self._assert_fl(user)
        ticket = self._get_ticket_or_404(ticket_id)

        if ticket.get("freelancer_id") != user.get("user_id"):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the freelancer can update their ticket")

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
        try:
            if role == "SA":
                items = self.repo.get_all_tickets()
            elif role == "FL":
                items = self.repo.get_tickets_by_freelancer(user.get("user_id"))
            else:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed")
            logger.debug("Tickets listed: role=%s count=%s", role, len(items) if items else 0)
            return items
        except PyMongoError:
            logger.exception("Mongo error listing tickets: role=%s user=%s", role, user.get("user_id"))
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to list tickets")
