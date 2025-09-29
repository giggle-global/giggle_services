# app/routes/portfolio.py
from fastapi import APIRouter, Depends, Query, status
from typing import Dict, Any, Optional
from app.core.keycloak import get_current_user
from app.schemas.response import APIResponse, ok
from app.models.portfolio import ProjectCreate, ProjectUpdate
from app.services.portfolio import PortfolioService

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

def get_portfolio_service():
    return PortfolioService()


@router.post("/", response_model=APIResponse, status_code=201)
def create_project(payload: ProjectCreate, current_user: Dict[str, Any] = Depends(get_current_user), svc: PortfolioService = Depends(get_portfolio_service)):
    created = svc.create_project(payload, current_user.get("user_id"))
    return ok(created, "Project created", status_code=status.HTTP_201_CREATED)


@router.get("/", response_model=APIResponse)
def list_projects(limit: int = Query(50, ge=1, le=200), skip: int = 0, current_user: Dict[str, Any] = Depends(get_current_user), svc: PortfolioService = Depends(get_portfolio_service)):
    projects = svc.list_for_user(current_user.get("user_id"), limit, skip)
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
