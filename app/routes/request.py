# app/routes/request.py
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Body, status
from app.models.request import RequestCreate, RequestUpdate, RequestOut
from app.services.request import RequestService
from app.core.keycloak import get_current_user
from app.schemas.response import APIResponse, ok

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/requests", tags=["REQUESTS"])

def get_request_service() -> RequestService:
    return RequestService()

@router.post("/", response_model=APIResponse[RequestOut], status_code=status.HTTP_201_CREATED)
def send_request(data: RequestCreate, current_user: Dict[str, Any] = Depends(get_current_user), svc: RequestService = Depends(get_request_service)):
    logger.debug(f"Send request by user_id={current_user.get('user_id')} role={current_user.get('role')} to freelancer_id={data.freelancer_id}")
    if current_user["role"] != "CL":
        logger.warning("Non-client attempted to send request.")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only clients can send requests")
    created = svc.create_request(current_user["user_id"], data.freelancer_id)
    logger.info(f"Request created: id={getattr(created, 'id', None)} sender={current_user.get('user_id')} freelancer={data.freelancer_id}")
    return ok(data=created, message="Request sent", status_code=status.HTTP_201_CREATED)

@router.post("/{request_id}/cancel", response_model=APIResponse[RequestOut])
def cancel_request(request_id: str, current_user: Dict[str, Any] = Depends(get_current_user), svc: RequestService = Depends(get_request_service)):
    logger.debug(f"Cancel request: request_id={request_id} by user_id={current_user.get('user_id')}")
    cancelled = svc.cancel_request(request_id, current_user["user_id"])
    logger.info(f"Request cancelled: request_id={request_id}")
    return ok(data=cancelled, message="Request cancelled")

@router.get("/sent", response_model=APIResponse[List[RequestOut]])
def list_sent_requests(current_user: Dict[str, Any] = Depends(get_current_user), svc: RequestService = Depends(get_request_service)):
    logger.debug(f"List sent requests by user_id={current_user.get('user_id')} role={current_user.get('role')}")
    if current_user["role"] != "CL":
        logger.warning("Non-client attempted to view sent requests.")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only clients can view sent requests")
    items = svc.get_sent_requests(current_user["user_id"])
    logger.info(f"Sent requests fetched: count={len(items) if items else 0}")
    return ok(data=items, message="Sent requests fetched")

@router.get("/received", response_model=APIResponse[List[RequestOut]])
def list_received_requests(current_user: Dict[str, Any] = Depends(get_current_user), svc: RequestService = Depends(get_request_service)):
    logger.debug(f"List received requests by user_id={current_user.get('user_id')} role={current_user.get('role')}")
    if current_user["role"] != "FL":
        logger.warning("Non-freelancer attempted to view received requests.")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only freelancers can view received requests")
    items = svc.get_received_requests(current_user["user_id"])
    logger.info(f"Received requests fetched: count={len(items) if items else 0}")
    return ok(data=items, message="Received requests fetched")

@router.post("/{request_id}/respond", response_model=APIResponse[RequestOut])
def respond_request(request_id: str, accept: bool = Body(..., embed=True), current_user: Dict[str, Any] = Depends(get_current_user), svc: RequestService = Depends(get_request_service)):
    logger.debug(f"Respond to request: request_id={request_id} by user_id={current_user.get('user_id')} accept={accept}")
    if current_user["role"] != "FL":
        logger.warning("Non-freelancer attempted to respond to request.")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only freelancers can accept/reject requests")
    updated = svc.respond_request(request_id, current_user["user_id"], accept)
    logger.info(f"Request response saved: request_id={request_id} accept={accept}")
    return ok(data=updated, message="Request accepted" if accept else "Request rejected")
