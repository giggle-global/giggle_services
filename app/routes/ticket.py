from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.models.ticket import (
    TicketCreate, TicketUpdate, TicketStatusUpdate, TicketOut, TicketAdminResponse, TicketStatus
)
from app.services.ticket import TicketService
from app.core.keycloak import get_current_user
from app.services.user import UserService


router = APIRouter(prefix="/tickets", tags=["ticket"])
service = TicketService()

@router.post("/", response_model=TicketOut)
def create_ticket(data: TicketCreate, user=Depends(get_current_user)):
    if user["role"] != "FL":
        raise HTTPException(403, "Only freelancers can raise tickets")
    client_id_check = UserService().get_user(data.client_id)
    if not client_id_check:
        raise HTTPException(404, "Client not found")
    if client_id_check["role"] != "CL":
        raise HTTPException(400, "Invalid client ID")
    return service.create_ticket(freelancer_id=user["user_id"], client_id=data.client_id, subject=data.subject, description=data.description, user=user)

@router.put("/{ticket_id}", response_model=TicketOut)
def update_ticket(ticket_id: str, data: TicketUpdate, user=Depends(get_current_user)):
    return service.update_ticket(ticket_id, data, user)

@router.patch("/{ticket_id}/status", response_model=TicketOut)
def update_ticket_status(ticket_id: str, data: TicketStatusUpdate, user=Depends(get_current_user)):
    return service.update_ticket_status(ticket_id, data.status, user)

@router.get("/", response_model=List[TicketOut])
def list_tickets(user=Depends(get_current_user)):
    return service.list_tickets(user)

@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: str, user=Depends(get_current_user)):
    return service.get_ticket(ticket_id, user)

@router.post("/{ticket_id}/admin-respond", response_model=TicketOut)
def admin_respond(ticket_id: str, data: TicketAdminResponse, user=Depends(get_current_user)):
    if user["role"] != "SA":
        raise HTTPException(403, "Only super admin can respond and close the ticket")
    return service.admin_respond(ticket_id, data, user)
