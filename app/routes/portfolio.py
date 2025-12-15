# app/routes/portfolio.py
from fastapi import APIRouter, Depends, Query, status, HTTPException
from typing import Dict, Any, Optional
import logging
from app.core.keycloak import get_current_user
from app.schemas.response import APIResponse, ok
from app.models.portfolio import ProjectCreate, ProjectUpdate
from app.services.portfolio import PortfolioService
from app.services.user import UserService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

def get_portfolio_service():
    return PortfolioService()


@router.post("/", response_model=APIResponse, status_code=201)
def create_project(payload: ProjectCreate, current_user: Dict[str, Any] = Depends(get_current_user), svc: PortfolioService = Depends(get_portfolio_service)):
    created = svc.create_project(payload, current_user.get("user_id"))
    return ok(created, "Project created", status_code=status.HTTP_201_CREATED)


@router.get("/", response_model=APIResponse)
def list_projects(
    limit: int = Query(50, ge=1, le=200),
    skip: int = 0,
    user_id: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: PortfolioService = Depends(get_portfolio_service),
):
    requester_role = current_user.get("role")
    requested_user_id = user_id or current_user.get("user_id")
    
    # If viewing someone else's portfolio, check permissions
    if user_id and user_id != current_user.get("user_id"):
        # Super Admin can view any portfolio
        if requester_role == "SA":
            pass  # Allow
        # Clients can view freelancer portfolios
        elif requester_role == "CL":
            # Verify the target user is a freelancer
            user_svc = UserService()
            target_user = user_svc.get_user(user_id=user_id)
            if target_user.get("role") != "FL" or target_user.get("status") != "ACTIVE":
                logger.warning(
                    "Client attempted to view unauthorized portfolio. requester=%s target_role=%s target_status=%s",
                    current_user.get("user_id"),
                    target_user.get("role"),
                    target_user.get("status")
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, 
                    detail="Clients can only view active freelancer portfolios"
                )
        else:
            # Others can only view their own portfolio
            logger.warning(
                "Unauthorized portfolio access attempt. requester_role=%s requester=%s target=%s",
                requester_role,
                current_user.get("user_id"),
                user_id
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Not allowed to view this portfolio"
            )

    projects = svc.list_for_user(requested_user_id, limit, skip)
    return ok(projects, "Projects fetched", status_code=status.HTTP_200_OK)


@router.get("/{project_id}", response_model=APIResponse)
def get_project(project_id: str, current_user: Dict[str, Any] = Depends(get_current_user), svc: PortfolioService = Depends(get_portfolio_service)):
    project = svc.get_project(project_id, current_user.get("user_id"))
    return ok(project, "Project fetched", status_code=status.HTTP_200_OK)


@router.put("/{project_id}", response_model=APIResponse)
def update_project(project_id: str, payload: ProjectUpdate, current_user: Dict[str, Any] = Depends(get_current_user), svc: PortfolioService = Depends(get_portfolio_service)):
    updated = svc.update_project(project_id, payload, current_user.get("user_id"))
    return ok(updated, "Project updated", status_code=status.HTTP_200_OK)


@router.post("/{project_id}/delete", response_model=APIResponse)
def delete_project(project_id: str, current_user: Dict[str, Any] = Depends(get_current_user), svc: PortfolioService = Depends(get_portfolio_service)):
    deleted = svc.delete_project(project_id, current_user.get("user_id"))
    return ok(deleted, "Project deleted", status_code=status.HTTP_200_OK)
