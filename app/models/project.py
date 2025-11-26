from pydantic import BaseModel, Field
from typing import Optional, Dict
from enum import Enum

class ProjectStatus(str, Enum):
    enabled = "enabled"
    disabled = "disabled"
    deleted = "deleted"

class LocationRequirement(str, Enum):
    """Location requirement preference for matching"""
    SAME_CITY = "same_city"
    SAME_REGION = "same_region"
    SAME_COUNTRY = "same_country"
    ANYWHERE = "anywhere"

class ProjectBase(BaseModel):
    title: str = Field(..., example="CareKonnect")
    platform: str = Field(..., example="Web/Mobile")
    duration: int = Field(..., example=6, description="Duration in months")
    design_status: str = Field(..., example="In Progress")
    budget: float = Field(..., example=5000.00)
    client_id: Optional[str] = Field(None, example="client-123")
    
    # Matching algorithm fields
    industry: Optional[str] = Field(None, example="Website Development", description="Industry/type of work")
    background_industry: Optional[str] = Field(None, example="F&B", description="Client's industry background")
    timeline_weeks: Optional[int] = Field(None, example=4, description="Timeline in weeks")
    required_location: Optional[Dict[str, str]] = Field(
        None, 
        example={"city": "Mumbai", "region": "Maharashtra", "country": "India"},
        description="Required location for freelancer"
    )
    location_preference: Optional[LocationRequirement] = Field(
        LocationRequirement.ANYWHERE,
        example="same_city",
        description="How strict the location requirement is"
    )

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(ProjectBase):
    title: Optional[str] = None
    platform: Optional[str] = None
    duration: Optional[int] = None
    design_status: Optional[str] = None
    budget: Optional[float] = None
    industry: Optional[str] = None
    background_industry: Optional[str] = None
    timeline_weeks: Optional[int] = None
    required_location: Optional[Dict[str, str]] = None
    location_preference: Optional[LocationRequirement] = None

class ProjectOut(ProjectBase):
    id: str
    status: ProjectStatus = ProjectStatus.enabled
