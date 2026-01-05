import os
import uuid
import re
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.aws_utils import (
    generate_s3_presigned_post,
    generate_s3_presigned_urls_for_object,
)
from app.core.keycloak import get_current_user

router = APIRouter(prefix="/storage", tags=["STORAGE"])

S3_BUCKET = os.getenv("S3_BUCKET") or os.getenv("AWS_BUCKET")
S3_REGION = os.getenv("S3_REGION") or os.getenv("AWS_REGION")
MAX_SIZE_BYTES = int(os.getenv("S3_MAX_UPLOAD_BYTES", "10485760"))  # 10 MB default


def _ensure_bucket_configured():
    if not S3_BUCKET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="S3 bucket not configured (set S3_BUCKET env var)",
        )


def _safe_filename(name: str) -> str:
    # Allow alnum, dot, dash, underscore; strip others
    clean = re.sub(r"[^A-Za-z0-9._-]", "_", name.strip())
    return clean or "file"


class ChatPresignRequest(BaseModel):
    group_type: str = Field(..., description="project | agreement | private")
    group_id: str = Field(..., description="chat room identifier")
    file_name: str
    content_type: str


class TicketPresignRequest(BaseModel):
    ticket_id: str
    file_name: str
    content_type: str


class PortfolioPresignRequest(BaseModel):
    project_id: str = Field(..., description="portfolio project identifier")
    file_name: str
    content_type: str


def _build_key(prefix: str, user_id: str, suffix: str) -> str:
    return f"uploads/{prefix}/{user_id}/{suffix}"


@router.post("/presign/chat")
def presign_chat_upload(
    payload: ChatPresignRequest,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Issue a presigned POST for chat attachments.
    The frontend should upload directly to S3, then send the chat message with the returned key.
    """
    _ensure_bucket_configured()

    group_type = payload.group_type.lower()
    if group_type not in {"project", "agreement", "private"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid group_type")

    safe_name = _safe_filename(payload.file_name)
    key_suffix = f"{group_type}/{payload.group_id}/{uuid.uuid4()}-{safe_name}"
    key = _build_key("chat", user.get("user_id") or "unknown", key_suffix)

    # Restrict Content-Type and max size (via conditions)
    post = generate_s3_presigned_post(
        bucket=S3_BUCKET,
        key=key,
        expires_in=900,  # 15 minutes
        content_type_startswith=payload.content_type.split("/")[0] + "/",
        region_name=S3_REGION,
        s3_client=None,
        extra_conditions=[["content-length-range", 1, MAX_SIZE_BYTES]],
    )

    urls = generate_s3_presigned_urls_for_object(
        bucket=S3_BUCKET,
        key=key,
        expires_in=3600,
        region_name=S3_REGION,
    )

    return {
        "key": key,
        "upload": post,
        "view_url": urls["view_url"],
        "download_url": urls["download_url"],
        "max_size_bytes": MAX_SIZE_BYTES,
    }


@router.post("/presign/ticket")
def presign_ticket_upload(
    payload: TicketPresignRequest,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Issue a presigned POST for ticket attachments (raise-dispute flow).
    """
    _ensure_bucket_configured()

    safe_name = _safe_filename(payload.file_name)
    key_suffix = f"{payload.ticket_id}/{uuid.uuid4()}-{safe_name}"
    key = _build_key("ticket", user.get("user_id") or "unknown", key_suffix)

    post = generate_s3_presigned_post(
        bucket=S3_BUCKET,
        key=key,
        expires_in=900,
        content_type_startswith=payload.content_type.split("/")[0] + "/",
        region_name=S3_REGION,
        extra_conditions=[["content-length-range", 1, MAX_SIZE_BYTES]],
    )

    urls = generate_s3_presigned_urls_for_object(
        bucket=S3_BUCKET,
        key=key,
        expires_in=3600,
        region_name=S3_REGION,
    )

    return {
        "key": key,
        "upload": post,
        "view_url": urls["view_url"],
        "download_url": urls["download_url"],
        "max_size_bytes": MAX_SIZE_BYTES,
    }


@router.post("/presign/portfolio")
def presign_portfolio_upload(
    payload: PortfolioPresignRequest,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Issue a presigned POST for portfolio PDF uploads.
    The frontend should upload directly to S3, then update the portfolio project with the returned key.
    """
    _ensure_bucket_configured()

    safe_name = _safe_filename(payload.file_name)
    key_suffix = f"{payload.project_id}/{uuid.uuid4()}-{safe_name}"
    key = _build_key("portfolio", user.get("user_id") or "unknown", key_suffix)

    post = generate_s3_presigned_post(
        bucket=S3_BUCKET,
        key=key,
        expires_in=900,  # 15 minutes
        content_type_startswith=payload.content_type.split("/")[0] + "/",
        region_name=S3_REGION,
        s3_client=None,
        extra_conditions=[["content-length-range", 1, MAX_SIZE_BYTES]],
    )

    urls = generate_s3_presigned_urls_for_object(
        bucket=S3_BUCKET,
        key=key,
        expires_in=3600,
        region_name=S3_REGION,
    )

    return {
        "key": key,
        "upload": post,
        "view_url": urls["view_url"],
        "download_url": urls["download_url"],
        "max_size_bytes": MAX_SIZE_BYTES,
    }


@router.get("/presign/portfolio/{project_id}")
def get_portfolio_pdf_url(
    project_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Get presigned URL for viewing/downloading a portfolio PDF.
    Allows portfolio owner, admins, or clients viewing freelancer portfolios.
    """
    _ensure_bucket_configured()
    
    # Import here to avoid circular dependency
    from app.services.portfolio import PortfolioService
    from app.services.user import UserService
    
    portfolio_service = PortfolioService()
    
    # Get project - need to check permissions
    try:
        project = portfolio_service.repo.get_by_id(project_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio project not found"
        )
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio project not found"
        )
    
    # Check permissions: owner, admin, or client viewing freelancer portfolio
    requester_id = user.get("user_id")
    requester_role = user.get("role")
    project_owner_id = project.get("user_id")
    
    has_access = False
    if project_owner_id == requester_id:
        has_access = True  # Owner
    elif requester_role == "SA":
        has_access = True  # Super Admin
    elif requester_role == "CL":
        # Client viewing freelancer portfolio - verify target is freelancer
        user_service = UserService()
        try:
            target_user = user_service.get_user(user_id=project_owner_id)
            if target_user.get("role") == "FL" and target_user.get("status") == "ACTIVE":
                has_access = True
        except Exception:
            pass
    
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not allowed to view this portfolio PDF"
        )
    
    if not project.get("portfolio_pdf"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio PDF not found for this project"
        )
    
    pdf_key = project.get("portfolio_pdf")
    
    urls = generate_s3_presigned_urls_for_object(
        bucket=S3_BUCKET,
        key=pdf_key,
        expires_in=3600,  # 1 hour
        region_name=S3_REGION,
        response_content_type="application/pdf",
    )
    
    return {
        "view_url": urls["view_url"],
        "download_url": urls["download_url"],
    }

