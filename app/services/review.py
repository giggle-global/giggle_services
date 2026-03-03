# app/services/review.py
import logging
from typing import List, Optional
from fastapi import HTTPException
from app.repositories.review import ReviewRepository
from app.repositories.user import UserRepository
from app.repositories.agreements import AgreementRepository
from app.repositories.project import ProjectRepository
from app.repositories.milestones import MilestoneRepository
from app.repositories.portfolio import PortfolioRepository
from app.models.review import ReviewCreate, ReviewUpdate, ReviewOut, RoleEnum
from app.models.milestones import MilestoneStatus
from app.services.notification import NotificationService
from app.models.notification import NotificationType

logger = logging.getLogger(__name__)

class ReviewService:
    def __init__(self, repo: Optional[ReviewRepository] = None):
        self.repo = repo or ReviewRepository()
        self.user_repo = UserRepository()
        self.agreement_repo = AgreementRepository()
        self.project_repo = ProjectRepository()
        self.milestone_repo = MilestoneRepository()
        self.portfolio_repo = PortfolioRepository()
        self.notification_service = NotificationService()

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
        
        # # Notify freelancer that client has given a review
        # try:
        #     agreement = self.agreement_repo.get_by_id(review_in.gig_id)
        #     if agreement:
        #         freelancer_id = agreement.get("freelancer", {}).get("user_id")
        #         if freelancer_id:
        #             # Get client name from agreement or full_client
        #             client_name = agreement.get("client", {}).get("name") or full_client.get("first_name", "") + " " + full_client.get("last_name", "")
        #             client_name = client_name.strip() or "Client"
        #             
        #             # Get project name from project_data
        #             project_name = project_data.get("title") or project_data.get("project_title") or "Project"
        #             
        #             # When freelancer receives a review, route them to the milestone
        #             # view for this agreement so they can see the review details.
        #             self.notification_service.create_notification(
        #                 user_id=freelancer_id,
        #                 notification_type=NotificationType.AGREEMENT_UPDATED,
        #                 title="Review Received",
        #                 message=f"{client_name} has given a review for the project '{project_name}'",
        #                 data={"agreement_id": review_in.gig_id, "type": "review_received", "client_name": client_name, "project_name": project_name},
        #                 link=f"/creator/milestone?agreement_id={review_in.gig_id}&view_review=true",
        #             )
        # except Exception as e:
        #     logger.warning(f"Failed to send notification to freelancer after review creation: {e}")
        
        # Check if all milestones are completed with payment received, and if so, mark agreement as Completed
        self._check_and_complete_agreement(review_in.gig_id)
        
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
    
    def _check_and_complete_agreement(self, agreement_id: str) -> None:
        """Check if all milestones are completed with payment received, and if so,
        mark agreement as Completed and notify both client and freelancer."""
        try:
            # Get agreement
            agreement = self.agreement_repo.get_by_id(agreement_id)
            if not agreement:
                logger.warning(f"Agreement {agreement_id} not found when checking completion")
                return
            
            # Check if agreement is already completed
            if agreement.get("status") == "Completed":
                return
            
            # Get all milestones for this agreementl
            milestones = self.milestone_repo.list_for_agreement(agreement_id)
            
            # Check if all milestones are completed with payment received (if milestones exist)
            # For agreements without milestones, consider them automatically eligible for completion
            def _is_fully_completed(m):
                """Check if milestone is completed with payment received"""
                s = m.get("status")
                is_completed_status = (s == MilestoneStatus.COMPLETED or str(s) == str(MilestoneStatus.COMPLETED))
                has_payment_received = m.get("payment_received", False)
                return is_completed_status and has_payment_received
            
            # If there are no milestones, consider the agreement ready for completion
            # If there are milestones, all must be fully completed
            all_fully_completed = not milestones or len(milestones) == 0 or all(_is_fully_completed(m) for m in milestones)
            
            if all_fully_completed:
                # All milestones are completed with payment received, mark agreement as Completed
                updated_agreement = self.agreement_repo.update(agreement_id, {"status": "Completed"})

                # Send completion notifications to both parties.
                # Use the freshly-updated agreement data if available, otherwise fall back
                # to the previously-fetched agreement document.
                try:
                    ag = updated_agreement or agreement
                    client_id = ag.get("client", {}).get("user_id")
                    freelancer_id = ag.get("freelancer", {}).get("user_id")

                    # Resolve project and name for contextual notification text
                    project = None
                    project_name = None
                    project_id = ag.get("project_id")
                    if project_id:
                        try:
                            project = self.project_repo.find_by_id(project_id)
                            if project:
                                project_name = project.get("title") or project.get("project_title")
                        except Exception:
                            project = None
                            project_name = None

        #             # Notify client that the agreement is fully completed
        #             if client_id:
        #                 self.notification_service.create_notification(
        #                     user_id=client_id,
        #                     notification_type=NotificationType.AGREEMENT_COMPLETED,
        #                     title="Agreement Completed",
        #                     message=(
        #                         f'Work for project "{project_name}" has been fully completed.'
        #                         if project_name
        #                         else "Work for this project has been fully completed."
        #                     ),
        #                     data={
        #                         "agreement_id": agreement_id,
        #                         "project_id": project_id,
        #                         "project_name": project_name,
        #                         "type": "agreement_completed",
        #                     },
        #                     # Client messages page with agreement context
        #                     link=f"/owner/messages?agreement_id={agreement_id}",
        #                 )
        # 
        #             # Notify freelancer that the agreement is fully completed
        #             if freelancer_id:
        #                 self.notification_service.create_notification(
        #                     user_id=freelancer_id,
        #                     notification_type=NotificationType.AGREEMENT_COMPLETED,
        #                     title="Agreement Completed",
        #                     message=(
        #                         f'Work for project "{project_name}" has been fully completed.'
        #                         if project_name
        #                         else "Work for this project has been fully completed."
        #                     ),
        #                     data={
        #                         "agreement_id": agreement_id,
        #                         "project_id": project_id,
        #                         "project_name": project_name,
        #                         "type": "agreement_completed",
        #                     },
        #                     # Freelancer gig page with agreement context, navigate to archive tab
        #                     link=f"/creator/gig?agreement_id={agreement_id}&tab=1",
        #                 )

                    # Auto-create or update freelancer portfolio entry for this project
                    try:
                        if freelancer_id and project_id and project:
                            description = (
                                project.get("scope_summary")
                                or project.get("description")
                                or ""
                            )
                            technologies = project.get("key_features") or []
                            portfolio_payload = {
                                "title": project_name or "Project",
                                "description": description,
                                "technologies": technologies,
                                "github_link": None,
                                "portfolio_link": None,
                            }

                            self.portfolio_repo.upsert_auto_project_from_source(
                                user_id=freelancer_id,
                                source_project_id=project_id,
                                base_payload=portfolio_payload,
                            )
                    except Exception as portfolio_err:
                        # Do not fail completion if portfolio upsert fails
                        logger.warning(
                            "Failed to upsert portfolio entry for agreement %s: %s",
                            agreement_id,
                            portfolio_err,
                        )
                except Exception as notif_err:
                    # Do not fail review flow if notifications cannot be sent
                    logger.warning(
                        "Failed to send agreement completion notifications for %s: %s",
                        agreement_id,
                        notif_err,
                    )
        except Exception as e:
            # Log error but don't fail the review creation
            logger.warning(f"Failed to check and complete agreement {agreement_id}: {e}")

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
