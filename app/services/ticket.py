from app.repositories.ticket import TicketRepository
from app.models.ticket import (
    TicketCreate, TicketUpdate, TicketStatusUpdate, TicketOut, TimelineEntry,
    TimelineAction, TicketStatus, TicketAdminResponse
)
from fastapi import HTTPException
import datetime

class TicketService:
    def __init__(self, repo: TicketRepository = None):
        self.repo = repo or TicketRepository()

    def create_ticket(self, freelancer_id, client_id, subject, description, user):
        timeline = [TimelineEntry(
            action=TimelineAction.CREATED,
            user_id=user["user_id"],
            user_role=user["role"],
            comment="Ticket created"
        ).model_dump()]
        data = {
            "freelancer_id": freelancer_id,
            "client_id": client_id,
            "subject": subject,
            "description": description,
            "status": TicketStatus.OPEN,
            "solution": None,
            "timeline": timeline
        }
        return self.repo.create_ticket(data)

    def update_ticket(self, ticket_id: str, update: TicketUpdate, user):
        ticket = self.repo.get_ticket(ticket_id)
        if not ticket or ticket["freelancer_id"] != user["user_id"]:
            raise HTTPException(403, "Only the freelancer can update their ticket.")
        update_dict = update.model_dump(exclude_unset=True)
        self.repo.update_ticket(ticket_id, update_dict)
        self.repo.add_timeline_entry(ticket_id, TimelineEntry(
            action=TimelineAction.UPDATED,
            user_id=user["user_id"],
            user_role=user["role"],
            comment="Ticket updated"
        ).model_dump())
        return self.repo.get_ticket(ticket_id)

    def update_ticket_status(self, ticket_id: str, status: TicketStatus, user):
        ticket = self.repo.get_ticket(ticket_id)
        if not ticket:
            raise HTTPException(404, "Ticket not found")
        # Logic: Freelancer can reopen, super admin can close/resolve/in progress
        if user["role"] == "FL" and status == TicketStatus.REOPENED:
            if ticket["status"] != TicketStatus.CLOSED:
                raise HTTPException(400, "Can only reopen a closed ticket.")
        elif user["role"] == "SA":
            if status not in [TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED, TicketStatus.CLOSED]:
                raise HTTPException(400, "Invalid status for admin.")
        else:
            raise HTTPException(403, "Not authorized.")
        self.repo.update_ticket(ticket_id, {"status": status})
        self.repo.add_timeline_entry(ticket_id, TimelineEntry(
            action=TimelineAction.STATUS_CHANGED,
            user_id=user["user_id"],
            user_role=user["role"],
            status=status,
            comment=f"Status changed to {status.value}"
        ).model_dump())
        return self.repo.get_ticket(ticket_id)

    def admin_respond(self, ticket_id: str, response: TicketAdminResponse, user):
        ticket = self.repo.get_ticket(ticket_id)
        if not ticket or user["role"] != "SA":
            raise HTTPException(403, "Only super admin can respond.")
        self.repo.update_ticket(ticket_id, {
            "solution": response.comment,
            "status": TicketStatus.CLOSED
        })
        self.repo.add_timeline_entry(ticket_id, TimelineEntry(
            action=TimelineAction.ADMIN_COMMENT,
            user_id=user["user_id"],
            user_role=user["role"],
            comment=response.comment,
            status=TicketStatus.CLOSED
        ).model_dump())
        return self.repo.get_ticket(ticket_id)

    def get_ticket(self, ticket_id: str, user):
        ticket = self.repo.get_ticket(ticket_id)
        if not ticket:
            raise HTTPException(404, "Ticket not found")
        # Freelancer can only see their ticket, SA can see all
        if user["role"] == "FL" and ticket["freelancer_id"] != user["user_id"]:
            raise HTTPException(403, "Not allowed.")
        return ticket

    def list_tickets(self, user):
        if user["role"] == "SA":
            return self.repo.get_all_tickets()
        elif user["role"] == "FL":
            return self.repo.get_tickets_by_freelancer(user["user_id"])
        else:
            raise HTTPException(403, "Not allowed.")
