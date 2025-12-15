import uuid
from fastapi import HTTPException, status
from typing import List
from datetime import datetime
from app.models.project import ProjectCreate, ProjectUpdate, ProjectOut, ProjectStatus
from app.repositories.project import ProjectRepository

class ProjectService:
    def __init__(self):
        self.repo = ProjectRepository()

    def create(self, payload: ProjectCreate, current_user: dict) -> ProjectOut:
        project_id = str(uuid.uuid4())
        doc = {
            "id": project_id,
            "title": payload.title,
            "platform": payload.platform,
            "duration": payload.duration,
            "design_status": payload.design_status,
            "budget": payload.budget,
            "status": ProjectStatus.enabled.value,
            "created_by": current_user.get("id"),
            "created_at": int(datetime.utcnow().timestamp()),
        }
        # Optional matching fields
        optional_fields = (
            "industry",
            "background_industry",
            "timeline_weeks",
            "required_location",
            "location_preference",
            "scope_summary",
            "content_sections",
            "key_features",
            "tone",
            "budget_min",
            "budget_max",
        )
        for field in optional_fields:
            value = getattr(payload, field, None)
            if value is not None:
                doc[field] = value
        self.repo.insert(doc)
        # Ensure created_at is included in the response
        project_dict = doc.copy()
        return ProjectOut(**project_dict)

    def get(self, project_id: str) -> ProjectOut:
        project = self.repo.find_by_id(project_id)
        if not project:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
        # Ensure has_review defaults to False if not present
        if "has_review" not in project:
            project["has_review"] = False
        return ProjectOut(**project)

    def list(self) -> List[ProjectOut]:
        projects = self.repo.find_all()
        return [ProjectOut(**p) for p in projects]

    def update(self, project_id: str, payload: ProjectUpdate, current_user: dict) -> ProjectOut:
        update_data = payload.dict(exclude_unset=True)
        if not update_data:
            return self.get(project_id)

        update_data["updated_by"] = current_user.get("id")

        matched = self.repo.update(project_id, update_data)
        if matched == 0:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
        project = self.repo.find_by_id(project_id)
        return ProjectOut(**project)

    def change_status(self, project_id: str, status: ProjectStatus, current_user: dict) -> ProjectOut:
        matched = self.repo.update_status(project_id, status.value)
        if matched == 0:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
        project = self.repo.find_by_id(project_id)
        return ProjectOut(**project)

    def delete(self, project_id: str) -> None:
        deleted = self.repo.delete(project_id)
        if deleted == 0:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

    def get_recent_projects(self, hours: int = 24, limit: int = 20) -> List[ProjectOut]:
        """Get projects created within the last N hours"""
        import logging
        logger = logging.getLogger(__name__)
        projects = self.repo.find_recent_projects(hours=hours, limit=limit)
        logger.info(f"Found {len(projects)} recent projects from repository")
        result = []
        for p in projects:
            # Log project data for debugging
            logger.info(f"Project {p.get('id')}: created_at={p.get('created_at')}, status={p.get('status')}")
            # Ensure created_at exists in the dict before creating ProjectOut
            if "created_at" in p:
                try:
                    project_out = ProjectOut(**p)
                    result.append(project_out)
                except Exception as e:
                    logger.error(f"Error creating ProjectOut for project {p.get('id')}: {e}")
        logger.info(f"Returning {len(result)} recent projects")
        return result
