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

# Import WebSocket manager from chat routes - use lazy import to avoid circular dependency
def get_websocket_manager():
    from app.routes import chat
    return chat.websocket_manager

def get_ticket_service() -> TicketService:
    return TicketService()

def get_user_service() -> UserService:
    return UserService()

@router.post("/", response_model=APIResponse[TicketOut], status_code=status.HTTP_201_CREATED)
async def create_ticket(
    data: TicketCreate,
    user: Dict[str, Any] = Depends(get_current_user),
    tickets: TicketService = Depends(get_ticket_service),
    users: UserService = Depends(get_user_service),
):
    logger.debug(f"Create ticket by user_id={user.get('user_id')} role={user.get('role')} payload={data.dict(exclude_none=True)}")

    caller_role = user.get("role")
    caller_id = user.get("user_id")

    # Determine who is the target and verify role compatibility
    if caller_role == "FL":
        # Freelancer calling -> must have provided client_id
        target_client_id = data.client_id
        # sanity: root_validator already ensured exactly one field provided
        if not target_client_id:
            logger.warning("Freelancer did not provide client_id.")
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "client_id is required for freelancer raising ticket")

        # can't raise ticket against self
        if target_client_id == caller_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot raise a ticket against yourself")

        target_user = users.get_user(target_client_id)
        if not target_user:
            logger.warning(f"Ticket creation failed: client not found client_id={target_client_id}")
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Client not found")
        if target_user.get("role") != "CL":
            logger.warning(f"Ticket creation failed: invalid target role client_id={target_client_id} role={target_user.get('role')}")
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Target user is not a client")

        # Create with appropriate params
        created = tickets.create_ticket(
            freelancer_id=caller_id,
            client_id=target_client_id,
            subject=data.subject,
            description=data.description,
            user=user,
            project_id=data.project_id,
            agreement_id=data.agreement_id,
        )

    elif caller_role == "CL":
        # Client calling -> must have provided freelancer_id
        target_freelancer_id = data.freelancer_id
        if not target_freelancer_id:
            logger.warning("Client did not provide freelancer_id.")
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "freelancer_id is required for client raising ticket")

        if target_freelancer_id == caller_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot raise a ticket against yourself")

        target_user = users.get_user(target_freelancer_id)
        if not target_user:
            logger.warning(f"Ticket creation failed: freelancer not found freelancer_id={target_freelancer_id}")
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Freelancer not found")
        if target_user.get("role") != "FL":
            logger.warning(f"Ticket creation failed: invalid target role freelancer_id={target_freelancer_id} role={target_user.get('role')}")
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Target user is not a freelancer")

        created = tickets.create_ticket(
            freelancer_id=target_freelancer_id,
            client_id=caller_id,
            subject=data.subject,
            description=data.description,
            user=user,
            project_id=data.project_id,
            agreement_id=data.agreement_id,
        )

    else:
        # other roles not allowed to raise tickets
        logger.warning(f"Unauthorized role attempted to raise ticket. user_id={caller_id} role={caller_role}")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only clients and freelancers can raise tickets")

    logger.info(f"Ticket created: id={getattr(created, 'id', None)} by={caller_id} against={target_user.get('user_id')}")
    
    # Broadcast dispute chat message via WebSocket if available
    if isinstance(created, dict) and created.get("_dispute_chat_message"):
        try:
            saved_message = created.pop("_dispute_chat_message")  # Remove from response
            request_id = created.pop("_dispute_request_id", None)
            project_id = created.pop("_dispute_project_id", None)
            
            if project_id and request_id and saved_message:
                # Broadcast to group (other participants)
                group_id = f"project::{project_id}"
                payload = {
                    "type": "message",
                    "payload": {
                        "group_type": "project",
                        "request_id": request_id,
                        "group_id": project_id,
                        "message": saved_message,
                    }
                }
                websocket_manager = get_websocket_manager()
                await websocket_manager.send_to_group(group_id, payload)
                logger.info(f"Dispute message broadcasted via WebSocket: project_id={project_id}")
        except Exception as e:
            # Don't fail ticket creation if WebSocket broadcast fails
            logger.exception(f"Error broadcasting dispute message via WebSocket: {str(e)}")
    
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

@router.get("/")
def list_tickets(user: Dict[str, Any] = Depends(get_current_user), tickets: TicketService = Depends(get_ticket_service)):
    try:
        logger.debug(f"List tickets for user_id={user.get('user_id')} role={user.get('role')}")
        items = tickets.list_tickets(user)
        logger.info(f"Tickets fetched: count={len(items) if items else 0}")
        
        # Ensure items is a list
        if not isinstance(items, list):
            items = []
        
        # Validate and clean items before returning
        cleaned_items = []
        if items:
            logger.debug(f"Processing {len(items)} tickets")
            for idx, item in enumerate(items):
                try:
                    if not isinstance(item, dict):
                        logger.warning(f"Ticket {idx} is not a dict, skipping")
                        continue
                    
                    # Quick validation - check required fields
                    required_fields = ["ticket_id", "freelancer_id", "client_id", "subject", "status"]
                    missing_fields = [field for field in required_fields if field not in item or item[field] is None]
                    if missing_fields:
                        logger.warning(f"Ticket {idx} missing required fields: {missing_fields}, ticket_id={item.get('ticket_id')}")
                        # Skip tickets with missing required fields
                        continue
                    
                    cleaned_items.append(item)
                except Exception as item_error:
                    logger.warning(f"Error processing ticket {idx}: {str(item_error)}")
                    continue
        
        logger.info(f"Returning {len(cleaned_items)} cleaned tickets")
        return ok(data=cleaned_items, message="Tickets fetched")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error in list_tickets route: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        # Return empty list instead of crashing
        return ok(data=[], message=f"Error fetching tickets: {str(e)}")

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

@router.get("/project/{project_id}/has-dispute", response_model=APIResponse[bool])
def check_dispute_by_project(project_id: str, user: Dict[str, Any] = Depends(get_current_user), tickets: TicketService = Depends(get_ticket_service)):
    """Check if there's an active dispute for a project"""
    logger.debug(f"Check dispute for project_id={project_id} by user_id={user.get('user_id')}")
    has_dispute = tickets.has_active_dispute(project_id)
    logger.info(f"Dispute check for project_id={project_id}: {has_dispute}")
    return ok(data=has_dispute, message="Dispute check completed")