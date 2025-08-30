from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

class ProjectStatus(str, Enum):
    enabled = "enabled"
    disabled = "disabled"
    deleted = "deleted"

class ProjectBase(BaseModel):
    title: str = Field(..., example="CareKonnect")
    platform: str = Field(..., example="Web/Mobile")
    duration: int = Field(..., example=6, description="Duration in months")
    design_status: str = Field(..., example="In Progress")
    budget: float = Field(..., example=5000.00)
    client_id: Optional[str] = Field(None, example="client-123")

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(ProjectBase):
    title: Optional[str] = None
    platform: Optional[str] = None
    duration: Optional[int] = None
    design_status: Optional[str] = None
    budget: Optional[float] = None

class ProjectOut(ProjectBase):
    id: str
    status: ProjectStatus = ProjectStatus.enabled
