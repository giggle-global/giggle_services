from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.models.request import RequestCreate, RequestUpdate, RequestOut
from app.services.request import RequestService
from app.core.keycloak import get_current_user

router = APIRouter(prefix="/requests", tags=["request"])
service = RequestService()

@router.post("/", response_model=RequestOut)
def send_request(data: RequestCreate, current_user=Depends(get_current_user)):
    if current_user["role"] != "CL":
        raise HTTPException(403, "Only clients can send requests")
    return service.create_request(current_user["user_id"], data.freelancer_id)

@router.post("/{request_id}/cancel", response_model=RequestOut)
def cancel_request(request_id: str, current_user=Depends(get_current_user)):
    return service.cancel_request(request_id, current_user["user_id"])

@router.get("/sent", response_model=List[RequestOut])
def list_sent_requests(current_user=Depends(get_current_user)):
    if current_user["role"] != "CL":
        raise HTTPException(403, "Only clients can view sent requests")
    return service.get_sent_requests(current_user["user_id"])

@router.get("/received", response_model=List[RequestOut])
def list_received_requests(current_user=Depends(get_current_user)):
    if current_user["role"] != "FL":
        raise HTTPException(403, "Only freelancers can view received requests")
    return service.get_received_requests(current_user["user_id"])

@router.post("/{request_id}/respond", response_model=RequestOut)
def respond_request(request_id: str, accept: bool, current_user=Depends(get_current_user)):
    print("current user role", current_user["role"])
    if current_user["role"] != "FL":
        raise HTTPException(403, "Only freelancers can accept/reject requests")
    return service.respond_request(request_id, current_user["user_id"], accept)
