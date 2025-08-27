# app/routes/ticket.py
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from app.models.ticket import TicketCreate, TicketUpdate, TicketStatusUpdate, TicketOut, TicketAdminResponse
from app.services.ticket import TicketService
from app.services.user import UserService
from app.core.keycloak import get_current_user
from app.schemas.response import APIResponse, ok

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tickets", tags=["TICKETS"])

def get_ticket_service() -> TicketService:
    return TicketService()

def get_user_service() -> UserService:
    return UserService()

@router.post("/", response_model=APIResponse[TicketOut], status_code=status.HTTP_201_CREATED)
def create_ticket(data: TicketCreate, user: Dict[str, Any] = Depends(get_current_user), tickets: TicketService = Depends(get_ticket_service), users: UserService = Depends(get_user_service)):
    logger.debug(f"Create ticket by user_id={user.get('user_id')} role={user.get('role')} for client_id={data.client_id}")
    if user["role"] != "FL":
        logger.warning("Non-freelancer attempted to raise ticket.")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only freelancers can raise tickets")
    client = users.get_user(data.client_id)
    if not client:
        logger.warning(f"Ticket creation failed: client not found client_id={data.client_id}")
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client not found")
    if client.get("role") != "CL":
        logger.warning(f"Ticket creation failed: invalid client role client_id={data.client_id}")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid client ID")
    created = tickets.create_ticket(freelancer_id=user["user_id"], client_id=data.client_id, subject=data.subject, description=data.description, user=user)
    logger.info(f"Ticket created: id={getattr(created, 'id', None)} freelancer={user.get('user_id')} client={data.client_id}")
    return ok(data=created, message="Ticket created", status_code=status.HTTP_201_CREATED)

@router.put("/{ticket_id}", response_model=APIResponse[TicketOut])
def update_ticket(ticket_id: str, data: TicketUpdate, user: Dict[str, Any] = Depends(get_current_user), tickets: TicketService = Depends(get_ticket_service)):
    logger.debug(f"Update ticket: ticket_id={ticket_id} by user_id={user.get('user_id')} payload={data.model_dump(exclude_unset=True)}")
    updated = tickets.update_ticket(ticket_id, data, user)
    logger.info(f"Ticket updated: ticket_id={ticket_id}")
    return ok(data=updated, message="Ticket updated")

@router.patch("/{ticket_id}/status", response_model=APIResponse[TicketOut])
def update_ticket_status(ticket_id: str, data: TicketStatusUpdate, user: Dict[str, Any] = Depends(get_current_user), tickets: TicketService = Depends(get_ticket_service)):
    logger.debug(f"Update ticket status: ticket_id={ticket_id} by user_id={user.get('user_id')} status={data.status}")
    updated = tickets.update_ticket_status(ticket_id, data.status, user)
    logger.info(f"Ticket status updated: ticket_id={ticket_id} status={data.status}")
    return ok(data=updated, message=f"Ticket status updated to {data.status}")

@router.get("/", response_model=APIResponse[List[TicketOut]])
def list_tickets(user: Dict[str, Any] = Depends(get_current_user), tickets: TicketService = Depends(get_ticket_service)):
    logger.debug(f"List tickets for user_id={user.get('user_id')} role={user.get('role')}")
    items = tickets.list_tickets(user)
    logger.info(f"Tickets fetched: count={len(items) if items else 0}")
    return ok(data=items, message="Tickets fetched")

@router.get("/{ticket_id}", response_model=APIResponse[TicketOut])
def get_ticket(ticket_id: str, user: Dict[str, Any] = Depends(get_current_user), tickets: TicketService = Depends(get_ticket_service)):
    logger.debug(f"Get ticket: ticket_id={ticket_id} by user_id={user.get('user_id')}")
    item = tickets.get_ticket(ticket_id, user)
    logger.info(f"Ticket fetched: ticket_id={ticket_id}")
    return ok(data=item, message="Ticket details fetched")

@router.post("/{ticket_id}/admin-respond", response_model=APIResponse[TicketOut])
def admin_respond(ticket_id: str, data: TicketAdminResponse, user: Dict[str, Any] = Depends(get_current_user), tickets: TicketService = Depends(get_ticket_service)):
    logger.debug(f"Admin respond: ticket_id={ticket_id} by user_id={user.get('user_id')} role={user.get('role')}")
    if user["role"] != "SA":
        logger.warning("Non-SA attempted to admin-respond to ticket.")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only super admin can respond and close the ticket")
    updated = tickets.admin_respond(ticket_id, data, user)
    logger.info(f"Admin response recorded: ticket_id={ticket_id}")
    return ok(data=updated, message="Admin response recorded")
