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
            
            # Generate thumbnail if PDF is provided
            if project.get("portfolio_pdf"):
                self._generate_thumbnail_if_needed(project)
                # Refresh project data to include the new cover_image
                project = self.repo.get_by_id(project.get("id"))
                
            return self._inject_presigned_urls(project)
        except PyMongoError:
            logger.exception("Mongo error creating portfolio project for user=%s", user_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to create project")

    def list_for_user(self, user_id: str, limit: int = 50, skip: int = 0) -> List[Dict[str, Any]]:
        if not user_id:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user_id is required")
        try:
            projects = self.repo.find_by_user(user_id, limit, skip)
            return [self._inject_presigned_urls(p) for p in projects]
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
        return self._inject_presigned_urls(project)

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
            # Maybe the user didn't change anything but still want to regenerate thumbnail?
            # For now, require some update
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nothing to update")

        try:
            updated = self.repo.update_project(project_id, update_payload)
            logger.info("Portfolio project updated id=%s by user=%s", project_id, user_id)
            
            # If PDF was updated, or if it exists and we're explicitly asked to refresh (optional)
            if "portfolio_pdf" in update_payload and updated.get("portfolio_pdf"):
                self._generate_thumbnail_if_needed(updated)
                # Refresh again
                updated = self.repo.get_by_id(project_id)
                
            return self._inject_presigned_urls(updated)
        except PyMongoError:
            logger.exception("Mongo error updating project id=%s", project_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to update project")

    def _inject_presigned_urls(self, project: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not project:
            return None
        
        doc = project.copy()
        cover_image_key = doc.get("cover_image")
        
        if cover_image_key:
            try:
                from app.core.aws_utils import generate_s3_presigned_get_url
                import os
                bucket = os.getenv("S3_BUCKET") or os.getenv("AWS_BUCKET")
                region = os.getenv("S3_REGION") or os.getenv("AWS_REGION")
                
                if bucket:
                    # Generate a presigned URL that is valid for 1 hour
                    doc["cover_image"] = generate_s3_presigned_get_url(
                        bucket=bucket,
                        key=cover_image_key,
                        expires_in=3600,
                        region_name=region,
                        inline=True,
                        response_content_type="image/png"
                    )
            except Exception as e:
                logger.warning("Failed to generate presigned URL for cover_image: %s", e)
                
        return doc

    def _generate_thumbnail_if_needed(self, project: Dict[str, Any]) -> None:
        pdf_key = project.get("portfolio_pdf")
        if not pdf_key:
            return

        import os
        bucket = os.getenv("S3_BUCKET") or os.getenv("AWS_BUCKET")
        if not bucket:
            logger.warning("S3_BUCKET not configured, skipping thumbnail generation")
            return

        # Generate thumbnail key: same directory as PDF
        # uploads/portfolio/{user_id}/{project_id}/{uuid}-{safe_name}
        # -> uploads/portfolio/{user_id}/{project_id}/thumbnail.png
        key_parts = pdf_key.split("/")
        if len(key_parts) >= 4:
            thumbnail_key = "/".join(key_parts[:-1]) + "/thumbnail.png"
        else:
            thumbnail_key = f"thumbnails/{project.get('id')}.png"

        try:
            from app.core.aws_utils import generate_pdf_thumbnail_to_s3
            generate_pdf_thumbnail_to_s3(bucket, pdf_key, thumbnail_key)
            
            # Update project with new cover_image (which is the thumbnail key)
            self.repo.update_project(project.get("id"), {"cover_image": thumbnail_key})
            logger.info("Generated thumbnail for project %s: %s", project.get("id"), thumbnail_key)
        except Exception as e:
            # Don't fail the whole request if thumbnail fails
            logger.warning("Failed to generate thumbnail for project %s: %s", project.get("id"), e)

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
