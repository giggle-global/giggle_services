# app/models/portfolio.py
from typing import Optional, List
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime
from enum import Enum

class PortfolioStatus(str, Enum):
    ACTIVE = "active"
    DELETED = "deleted"

class ProjectBase(BaseModel):
    title: str = Field(..., example="E-commerce Platform")
    description: Optional[str] = Field(None, example="Short description of the project")
    technologies: Optional[List[str]] = Field(None, example=["React", "Node.js", "MongoDB"])
    github_link: Optional[HttpUrl] = Field(None, example="https://github.com/username/repo")
    portfolio_link: Optional[HttpUrl] = Field(None, example="https://my-portfolio.example.com/project")
    cover_image: Optional[str] = Field(None, example="s3://bucket/key.png")  # store URL or S3 key  

    class Config:
        schema_extra = {
            "example": {
                "title": "E-commerce Platform",
                "description": "A full-featured e-commerce platform with shopping cart and payment integration.",
                "technologies": ["React", "Node.js", "MongoDB"],
                "github_link": "https://github.com/username/repo",
                "portfolio_link": "https://my-portfolio.example.com/project",
                "cover_image": "s3://bucket/key.png"
            }
        }

class ProjectCreate(ProjectBase):
    pass

    class config:
        schema_extra = {
            "example": {
                "title": "E-commerce Platform",
                "description": "A full-featured e-commerce platform with shopping cart and payment integration.",
                "technologies": ["React", "Node.js", "MongoDB"],
                "github_link": "https://github.com/username/repo",
                "portfolio_link": "https://my-portfolio.example.com/project",
                "cover_image": "s3://bucket/key.png"
            }
        }


class ProjectUpdate(BaseModel):
    title: Optional[str]
    description: Optional[str]
    technologies: Optional[List[str]]
    github_link: Optional[HttpUrl]
    portfolio_link: Optional[HttpUrl]
    cover_image: Optional[str]

    class config:
        schema_extra = {
            "example": {
                "title": "Updated E-commerce Platform",
                "description": "A full-featured e-commerce platform with updated features.",
                "technologies": ["React", "Node.js", "MongoDB"],
                "github_link": "https://github.com/username/repo",
                "portfolio_link": "https://my-portfolio.example.com/project",
                "cover_image": "s3://bucket/key.png"
            }
        }

class ProjectInDB(ProjectBase):
    id: str
    user_id: str
    status: PortfolioStatus
    created_at: datetime
    updated_at: datetime

class ProjectOut(ProjectInDB):
    pass
