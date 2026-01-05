# app/models/portfolio.py
from typing import Optional, List, Union
from pydantic import BaseModel, Field, HttpUrl, field_validator
from datetime import datetime
from enum import Enum

class PortfolioStatus(str, Enum):
    ACTIVE = "active"
    DELETED = "deleted"

class ProjectBase(BaseModel):
    title: str = Field(..., example="E-commerce Platform")
    description: Optional[str] = None
    technologies: Optional[List[str]] = None
    github_link: Optional[str] = None
    portfolio_link: Optional[str] = None
    cover_image: Optional[str] = None
    portfolio_pdf: Optional[str] = None  

    class Config:
        # Allow fields to be omitted from request body
        from_attributes = True
        json_schema_extra= {
            "example": {
                "title": "E-commerce Platform",
                "description": "A full-featured e-commerce platform with shopping cart and payment integration.",
                "technologies": ["React", "Node.js", "MongoDB"],
                "github_link": "https://github.com/username/repo",
                "portfolio_link": "https://my-portfolio.example.com/project",
                "cover_image": "s3://bucket/key.png",
                "portfolio_pdf": "s3://bucket/portfolio.pdf"
            }
        }

class ProjectCreate(ProjectBase):
    pass

    class config:
       json_schema_extra= {
            "example": {
                "title": "E-commerce Platform",
                "description": "A full-featured e-commerce platform with shopping cart and payment integration.",
                "technologies": ["React", "Node.js", "MongoDB"],
                "github_link": "https://github.com/username/repo",
                "portfolio_link": "https://my-portfolio.example.com/project",
                "cover_image": "s3://bucket/key.png",
                "portfolio_pdf": "s3://bucket/portfolio.pdf"
            }
        }


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    technologies: Optional[List[str]] = None
    github_link: Optional[str] = None
    portfolio_link: Optional[str] = None
    cover_image: Optional[str] = None
    portfolio_pdf: Optional[str] = None

    class config:
       json_schema_extra= {
            "example": {
                "title": "Updated E-commerce Platform",
                "description": "A full-featured e-commerce platform with updated features.",
                "technologies": ["React", "Node.js", "MongoDB"],
                "github_link": "https://github.com/username/repo",
                "portfolio_link": "https://my-portfolio.example.com/project",
                "cover_image": "s3://bucket/key.png",
                "portfolio_pdf": "s3://bucket/portfolio.pdf"
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
