# app/routes/request.py
from fastapi import APIRouter, Depends, HTTPException, Body, status
from typing import List, Dict, Any

from app.models.request import RequestCreate, RequestUpdate, RequestOut
from app.services.request import RequestService
from app.core.keycloak import get_current_user
from app.schemas.response import APIResponse, ok

router = APIRouter(prefix="/requests", tags=["REQUESTS"])
service = RequestService()

@router.post("/", response_model=APIResponse[RequestOut], status_code=status.HTTP_201_CREATED)
def send_request(data: RequestCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    if current_user["role"] != "CL":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only clients can send requests")
    created = service.create_request(current_user["user_id"], data.freelancer_id)
    return ok(data=created, message="Request sent", status_code=status.HTTP_201_CREATED)

@router.post("/{request_id}/cancel", response_model=APIResponse[RequestOut])
def cancel_request(request_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    # Optional: ensure only the sender cancels – your service can validate ownership
    cancelled = service.cancel_request(request_id, current_user["user_id"])
    return ok(data=cancelled, message="Request cancelled")

@router.get("/sent", response_model=APIResponse[List[RequestOut]])
def list_sent_requests(current_user: Dict[str, Any] = Depends(get_current_user)):
    if current_user["role"] != "CL":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only clients can view sent requests")
    items = service.get_sent_requests(current_user["user_id"])
    return ok(data=items, message="Sent requests fetched")

@router.get("/received", response_model=APIResponse[List[RequestOut]])
def list_received_requests(current_user: Dict[str, Any] = Depends(get_current_user)):
    if current_user["role"] != "FL":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only freelancers can view received requests")
    items = service.get_received_requests(current_user["user_id"])
    return ok(data=items, message="Received requests fetched")

@router.post("/{request_id}/respond", response_model=APIResponse[RequestOut])
def respond_request(
    request_id: str,
    accept: bool = Body(..., embed=True),  # expects {"accept": true/false}
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    if current_user["role"] != "FL":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only freelancers can accept/reject requests")
    updated = service.respond_request(request_id, current_user["user_id"], accept)
    return ok(data=updated, message="Request accepted" if accept else "Request rejected")
