# app/services/portfolio.py
import logging
from typing import Dict, Any, List, Optional
from fastapi import HTTPException, status
from pymongo.errors import PyMongoError

from app.repositories.portfolio import PortfolioRepository
from app.models.portfolio import ProjectCreate, ProjectUpdate, PortfolioStatus

logger = logging.getLogger(__name__)

class PortfolioService:
    def __init__(self, repo: Optional[PortfolioRepository] = None):
        self.repo = repo or PortfolioRepository()

    def create_project(self, payload: ProjectCreate, user_id: str) -> Dict[str, Any]:
        if not user_id:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user_id is required")

        to_insert = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        to_insert["user_id"] = user_id

        try:
            project = self.repo.create_project(to_insert)
            logger.info("Portfolio project created: id=%s user=%s", project.get("id"), user_id)
            return project
        except PyMongoError:
            logger.exception("Mongo error creating portfolio project for user=%s", user_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to create project")

    def list_for_user(self, user_id: str, limit: int = 50, skip: int = 0) -> List[Dict[str, Any]]:
        if not user_id:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user_id is required")
        try:
            return self.repo.find_by_user(user_id, limit, skip)
        except PyMongoError:
            logger.exception("Mongo error listing projects for user=%s", user_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to list projects")

    def get_project(self, project_id: str, user_id: str) -> Dict[str, Any]:
        if not project_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "project_id is required")
        try:
            project = self.repo.get_by_id(project_id)
        except PyMongoError:
            logger.exception("Mongo error fetching project id=%s", project_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to fetch project")

        if not project:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
        # allow owner or admin access - adjust role checks if needed (here only ownership)
        if project.get("user_id") != user_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to view this project")
        return project

    def update_project(self, project_id: str, payload: ProjectUpdate, user_id: str) -> Dict[str, Any]:
        if not project_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "project_id is required")
        try:
            existing = self.repo.get_by_id(project_id)
        except PyMongoError:
            logger.exception("Mongo error fetching project for update id=%s", project_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to fetch project")

        if not existing:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
        if existing.get("user_id") != user_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to update this project")
        if existing.get("status") == PortfolioStatus.DELETED.value:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot update deleted project")

        update_payload = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
        if not update_payload:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nothing to update")

        try:
            updated = self.repo.update_project(project_id, update_payload)
            logger.info("Portfolio project updated id=%s by user=%s", project_id, user_id)
            return updated
        except PyMongoError:
            logger.exception("Mongo error updating project id=%s", project_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to update project")

    def delete_project(self, project_id: str, user_id: str) -> Dict[str, Any]:
        if not project_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "project_id is required")
        try:
            existing = self.repo.get_by_id(project_id)
        except PyMongoError:
            logger.exception("Mongo error fetching project for delete id=%s", project_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to fetch project")

        if not existing:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
        if existing.get("user_id") != user_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to delete this project")
        if existing.get("status") == PortfolioStatus.DELETED.value:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Project already deleted")

        try:
            deleted = self.repo.soft_delete(project_id, user_id)
            logger.info("Portfolio project deleted id=%s by user=%s", project_id, user_id)
            return deleted
        except PyMongoError:
            logger.exception("Mongo error deleting project id=%s", project_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to delete project")
