# app/routes/ticket.py
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status

from app.models.ticket import (
    TicketCreate, TicketUpdate, TicketStatusUpdate, TicketOut, TicketAdminResponse
)
from app.services.ticket import TicketService
from app.services.user import UserService
from app.core.keycloak import get_current_user
from app.schemas.response import APIResponse, ok

router = APIRouter(prefix="/tickets", tags=["TICKETS"])

# ---- Dependency providers (nice for unit tests) ----
def get_ticket_service() -> TicketService:
    return TicketService()

def get_user_service() -> UserService:
    return UserService()

# ---- Routes ----

@router.post("/", response_model=APIResponse[TicketOut], status_code=status.HTTP_201_CREATED)
def create_ticket(
    data: TicketCreate,
    user: Dict[str, Any] = Depends(get_current_user),
    tickets: TicketService = Depends(get_ticket_service),
    users: UserService = Depends(get_user_service),
):
    # Only freelancers can raise tickets
    if user["role"] != "FL":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only freelancers can raise tickets")

    # Validate client
    client = users.get_user(data.client_id)
    if not client:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client not found")
    if client.get("role") != "CL":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid client ID")

    created = tickets.create_ticket(
        freelancer_id=user["user_id"],
        client_id=data.client_id,
        subject=data.subject,
        description=data.description,
        user=user,
    )
    return ok(data=created, message="Ticket created", status_code=status.HTTP_201_CREATED)


@router.put("/{ticket_id}", response_model=APIResponse[TicketOut])
def update_ticket(
    ticket_id: str,
    data: TicketUpdate,
    user: Dict[str, Any] = Depends(get_current_user),
    tickets: TicketService = Depends(get_ticket_service),
):
    updated = tickets.update_ticket(ticket_id, data, user)
    return ok(data=updated, message="Ticket updated")


@router.patch("/{ticket_id}/status", response_model=APIResponse[TicketOut])
def update_ticket_status(
    ticket_id: str,
    data: TicketStatusUpdate,
    user: Dict[str, Any] = Depends(get_current_user),
    tickets: TicketService = Depends(get_ticket_service),
):
    updated = tickets.update_ticket_status(ticket_id, data.status, user)
    return ok(data=updated, message=f"Ticket status updated to {data.status}")


@router.get("/", response_model=APIResponse[List[TicketOut]])
def list_tickets(
    user: Dict[str, Any] = Depends(get_current_user),
    tickets: TicketService = Depends(get_ticket_service),
):
    items = tickets.list_tickets(user)
    return ok(data=items, message="Tickets fetched")


@router.get("/{ticket_id}", response_model=APIResponse[TicketOut])
def get_ticket(
    ticket_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
    tickets: TicketService = Depends(get_ticket_service),
):
    item = tickets.get_ticket(ticket_id, user)
    return ok(data=item, message="Ticket details fetched")


@router.post("/{ticket_id}/admin-respond", response_model=APIResponse[TicketOut])
def admin_respond(
    ticket_id: str,
    data: TicketAdminResponse,
    user: Dict[str, Any] = Depends(get_current_user),
    tickets: TicketService = Depends(get_ticket_service),
):
    if user["role"] != "SA":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only super admin can respond and close the ticket")
    updated = tickets.admin_respond(ticket_id, data, user)
    return ok(data=updated, message="Admin response recorded")
