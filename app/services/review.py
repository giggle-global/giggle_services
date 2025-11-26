# app/services/review.py
import logging
from typing import List, Optional
from fastapi import HTTPException
from app.repositories.review import ReviewRepository
from app.repositories.user import UserRepository
from app.repositories.agreements import AgreementRepository
from app.repositories.project import ProjectRepository
from app.models.review import ReviewCreate, ReviewUpdate, ReviewOut, RoleEnum

logger = logging.getLogger(__name__)

class ReviewService:
    def __init__(self, repo: Optional[ReviewRepository] = None):
        self.repo = repo or ReviewRepository()
        self.user_repo = UserRepository()
        self.agreement_repo = AgreementRepository()
        self.project_repo = ProjectRepository()

    def create_review(self, review_in: ReviewCreate, current_user: dict) -> dict:
        # Only clients can create reviews
        if current_user.get("role") != RoleEnum.CLIENT.value:
            raise HTTPException(status_code=403, detail="Only clients can create reviews")
        # Ensure current_user is same as client_id
        if current_user.get("user_id") != review_in.client_id:
            raise HTTPException(status_code=403, detail="client_id mismatch")
        # Optionally: validate freelancer exists (repo or user service)
        full_client = self.user_repo.get_user_by_id(review_in.client_id)
        if not full_client:
            raise HTTPException(status_code=404, detail="Client not found")
        full_client_company_name = full_client.get("company_info", {}).get("company_name", "")
        review_in.client_company_name = full_client_company_name
        gig_data = self.agreement_repo.get_by_id(review_in.gig_id)
        if not gig_data:
            raise HTTPException(status_code=404, detail="Gig not found")
        review_in.gig_title = gig_data.get("title", "")
        
        # Get project_id from agreement if not provided
        if not review_in.project_id:
            review_in.project_id = gig_data.get("project_id")
            if not review_in.project_id:
                raise HTTPException(status_code=400, detail="Project ID is required and not found in agreement")
        
        # Validate project exists
        project_data = self.project_repo.find_by_id(review_in.project_id)
        if not project_data:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Create the review
        created_review = self.repo.create_review(review_in)
        
        # Update has_review flag on the project based on actual review count
        self._update_project_review_flag(review_in.project_id)
        
        return created_review
    
    def _update_project_review_flag(self, project_id: str) -> None:
        """Update the has_review flag on a project based on whether reviews exist"""
        try:
            review_count = self.repo.count_reviews_for_project(project_id)
            has_review = review_count > 0
            self.project_repo.update(project_id, {"has_review": has_review})
            logger.info(f"Updated has_review={has_review} for project {project_id} (review count: {review_count})")
        except Exception as e:
            # Log error but don't fail the operation
            logger.warning(f"Failed to update has_review flag for project {project_id}: {e}")

    def update_review(self, review_id: str, update: ReviewUpdate, current_user: dict) -> dict:
        if current_user.get("role") != RoleEnum.CLIENT.value:
            raise HTTPException(status_code=403, detail="Only clients can update reviews")
        update_data = update.model_dump(exclude_unset=True)
        return self.repo.update_review(review_id, update_data, current_user.get("user_id"))

    def delete_review(self, review_id: str, current_user: dict) -> None:
        if current_user.get("role") != RoleEnum.CLIENT.value:
            raise HTTPException(status_code=403, detail="Only clients can delete reviews")
        
        # Get the review first to get project_id before deleting
        review = self.repo.get_review(review_id)
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")
        
        project_id = review.get("project_id")
        
        # Delete the review
        self.repo.delete_review(review_id, current_user.get("user_id"))
        
        # Update has_review flag on the project based on remaining review count
        if project_id:
            self._update_project_review_flag(project_id)

    def get_review(self, review_id: str, current_user: dict) -> dict:
        # clients can view own reviews; freelancers can view reviews about them; SA can view all
        review = self.repo.get_review(review_id)
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")
        role = current_user.get("role")
        uid = current_user.get("user_id")
        if role == RoleEnum.SUPER_ADMIN.value:
            return review
        if role == RoleEnum.CLIENT.value and review.get("client_id") == uid:
            return review
        if role == RoleEnum.FREELANCER.value and review.get("freelancer_id") == uid:
            return review
        raise HTTPException(status_code=403, detail="Not authorized to view this review")

    def list_reviews_for_freelancer(self, freelancer_id: str, current_user: dict, limit: int = 50, skip: int = 0) -> List[dict]:
        # freelancers can see their own reviews; SA can see all
        role = current_user.get("role")
        uid = current_user.get("user_id")
        # import pdb; pdb.set_trace()
        if role == RoleEnum.SUPER_ADMIN.value or (role == RoleEnum.FREELANCER.value and uid == freelancer_id) or (role == RoleEnum.CLIENT.value):
            print("Fetching reviews for freelancer:", freelancer_id)
            return self.repo.list_reviews_for_freelancer(freelancer_id, limit, skip)
        raise HTTPException(status_code=403, detail="Not authorized")

    def list_reviews_by_client(self, client_id: str, current_user: dict, limit: int = 50, skip: int = 0) -> List[dict]:
        # client can list their reviews; SA can view any
        role = current_user.get("role")
        uid = current_user.get("user_id")
        if role == RoleEnum.SUPER_ADMIN.value or (role == RoleEnum.CLIENT.value and uid == client_id):
            return self.repo.list_reviews_by_client(client_id, limit, skip)
        raise HTTPException(status_code=403, detail="Not authorized")

    def average_rating(self, type: str, user_id: str, current_user: dict) -> float:
        role = current_user.get("role")
        uid = current_user.get("user_id")
        return self.repo.average_rating_for_freelancer(type, user_id)

        # if role == RoleEnum.SUPER_ADMIN.value or (role == RoleEnum.FREELANCER.value and uid == user_id):
        #     return self.repo.average_rating_for_freelancer(user_id)
        # raise HTTPException(status_code=403, detail="Not authorized")
