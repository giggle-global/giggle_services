import uuid
from fastapi import HTTPException, status
from typing import List
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
        }
        self.repo.insert(doc)
        return ProjectOut(**doc)

    def get(self, project_id: str) -> ProjectOut:
        project = self.repo.find_by_id(project_id)
        if not project:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
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
