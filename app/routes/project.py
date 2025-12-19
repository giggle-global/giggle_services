from fastapi import APIRouter, Depends, status, Query
from typing import List, Dict, Any
from app.models.project import ProjectCreate, ProjectUpdate, ProjectOut, ProjectStatus
from app.services.project import ProjectService
from app.schemas.response import APIResponse, ok
from app.core.keycloak import get_current_user

router = APIRouter(prefix="/projects", tags=["Projects"])

def get_project_service():
    return ProjectService()

@router.post("/", response_model=APIResponse[ProjectOut], status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    svc: ProjectService = Depends(get_project_service),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return ok(data=svc.create(payload, current_user), message="Project created")

@router.get("/recent", response_model=APIResponse[List[ProjectOut]])
def get_recent_projects(
    hours: int = Query(24, ge=1, le=168, description="Number of hours to look back (1-168)"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of projects to return"),
    svc: ProjectService = Depends(get_project_service),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get projects created within the last N hours (default 24 hours)"""
    return ok(
        data=svc.get_recent_projects(hours=hours, limit=limit, current_user=current_user),
        message="Recent projects fetched"
    )

@router.get("/", response_model=APIResponse[List[ProjectOut]])
def list_projects(
    svc: ProjectService = Depends(get_project_service),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return ok(data=svc.list(), message="Projects fetched")

@router.get("/{project_id}", response_model=APIResponse[ProjectOut])
def get_project(
    project_id: str,
    svc: ProjectService = Depends(get_project_service),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return ok(data=svc.get(project_id), message="Project fetched")

@router.put("/{project_id}", response_model=APIResponse[ProjectOut])
def update_project(
    project_id: str,
    payload: ProjectUpdate,
    svc: ProjectService = Depends(get_project_service),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return ok(data=svc.update(project_id, payload, current_user), message="Project updated")

@router.patch("/{project_id}/status", response_model=APIResponse[ProjectOut])
def change_status(
    project_id: str,
    status: ProjectStatus,
    svc: ProjectService = Depends(get_project_service),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return ok(data=svc.change_status(project_id, status, current_user), message=f"Project {status.value}")

@router.delete("/{project_id}", response_model=APIResponse[None])
def delete_project(
    project_id: str,
    svc: ProjectService = Depends(get_project_service),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    svc.delete(project_id)
    return ok(message="Project deleted")