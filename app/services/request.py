# app/services/request.py
import logging
from typing import Any, Dict, Optional
from fastapi import HTTPException, status
from pymongo.errors import PyMongoError

from app.repositories.request import RequestRepository
from app.repositories.user import UserRepository
from app.repositories.project import ProjectRepository
from app.models.request import RequestCreate, RequestUpdate, RequestOut, RequestStatus

logger = logging.getLogger(__name__)

# Maximum number of requests a client can send per project
MAX_REQUESTS_PER_PROJECT = 10


class RequestService:
    def __init__(self, repo: Optional[RequestRepository] = None, user_repo: Optional[UserRepository] = None):
        self.repo = repo or RequestRepository()
        self.user_repo = user_repo or UserRepository()
        self.project_repo = ProjectRepository()

    # ---------- Helpers ----------
    def _get_user_or_404(self, user_id: str) -> Dict[str, Any]:
        if not user_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "user_id is required")
        try:
            user = self.user_repo.get_user_by_id(user_id)
        except PyMongoError:
            logger.exception("Mongo error while fetching user_id=%s", user_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to fetch user")
        if not user:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
        return user

    # ---------- Create ----------
    def create_request(self, client_id: str, freelancer_id: str, project_id: str) -> Dict[str, Any]:
        if not client_id or not freelancer_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "client_id and freelancer_id are required")
        if client_id == freelancer_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Client and freelancer cannot be the same")

        client = self._get_user_or_404(client_id)
        if client.get("role") != "CL":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid client ID")

        freelancer = self._get_user_or_404(freelancer_id)
        if freelancer.get("role") != "FL":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid freelancer ID")
        
        if not project_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "project_id is required")
        
        project_details = self.project_repo.find_by_id(project_id=project_id)
        if not project_details:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Project not found or not associated with client")

        # Check request limit per project (10 PENDING requests per project)
        try:
            pending_requests = self.repo.count_pending_requests_by_client_and_project(client_id, project_id)
            if pending_requests >= MAX_REQUESTS_PER_PROJECT:
                logger.warning("Request limit exceeded: client=%s project=%s pending_requests=%s", client_id, project_id, pending_requests)
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"You have reached the maximum limit of {MAX_REQUESTS_PER_PROJECT} pending requests for this project. You cannot send more requests until some are accepted or rejected."
                )
        except PyMongoError:
            logger.exception("Mongo error checking pending requests: client=%s project=%s", client_id, project_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to verify request limit")

        try:
            if self.repo.request_exists(client_id, freelancer_id, project_id):
                # Get the existing request to check its status for a better error message
                existing_request = self.repo.get_request_by_parties(project_id, freelancer_id, client_id)
                if existing_request:
                    status = existing_request.get("status")
                    if status == RequestStatus.ACCEPTED.value:
                        logger.info("Duplicate request prevented (accepted exists): client=%s freelancer=%s project=%s", client_id, freelancer_id, project_id)
                        raise HTTPException(status.HTTP_409_CONFLICT, "You already have an accepted request with this freelancer for this project.")
                    else:
                        logger.info("Duplicate request prevented (pending exists): client=%s freelancer=%s project=%s", client_id, freelancer_id, project_id)
                        raise HTTPException(status.HTTP_409_CONFLICT, "You already have a pending request to this freelancer for this project.")
                else:
                    logger.info("Duplicate request prevented: client=%s freelancer=%s project=%s", client_id, freelancer_id, project_id)
                    raise HTTPException(status.HTTP_409_CONFLICT, "You have already sent a request to this freelancer for this project.")
        except HTTPException:
            # Re-raise HTTP exceptions (like the ones we just raised)
            raise
        except PyMongoError:
            logger.exception("Mongo error checking existing request: client=%s freelancer=%s project=%s", client_id, freelancer_id, project_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to verify request existence")

        try:
            created = self.repo.create_request(client_id, freelancer_id, client.get("first_name"), client.get("last_name"), freelancer.get("first_name"), freelancer.get("last_name"), project_id, project_name=project_details.get("title"))
            logger.info("Request created: id=%s client=%s freelancer=%s", getattr(created, "id", None), client_id, freelancer_id)
            
            # Check if this request reached the limit (5/5) and send notification to client
            try:
                new_pending_requests = self.repo.count_pending_requests_by_client_and_project(client_id, project_id)
                if new_pending_requests == MAX_REQUESTS_PER_PROJECT:
                    # Client just reached the limit (5/5) for this project, notify the client
                    try:
                        from app.services.notification import NotificationService
                        notification_service = NotificationService()
                        notification_service.notify_client_request_limit_reached(
                            client_id=client_id,
                            max_requests=MAX_REQUESTS_PER_PROJECT
                        )
                        logger.info("Limit reached notification sent to client: %s project=%s (reached %d/%d)", client_id, project_id, new_pending_requests, MAX_REQUESTS_PER_PROJECT)
                    except Exception as e:
                        logger.warning("Failed to send limit reached notification: %s", e)
                        # Don't fail the request creation if notification fails
            except Exception as e:
                logger.warning("Failed to check pending requests after creation: %s", e)
                # Continue even if check fails
            
            # Send notification to freelancer about new request received
            try:
                from app.services.notification import NotificationService
                notification_service = NotificationService()
                notification_service.notify_request_received(
                    freelancer_id=freelancer_id,
                    client_name=f"{client.get('first_name', '')} {client.get('last_name', '')}".strip(),
                    project_title=project_details.get("title", "Project"),
                    request_id=created.get("request_id"),
                    project_id=project_id
                )
                logger.info("Notification sent to freelancer: %s", freelancer_id)
            except Exception as e:
                logger.warning("Failed to send notification (request still created): %s", e)
                # Don't fail the request creation if notification fails
            
            return created
        except PyMongoError:
            logger.exception("Mongo error creating request: client=%s freelancer=%s", client_id, freelancer_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to create request")

    # ---------- Lists ----------
    def get_sent_requests(self, client_id: str):
        if not client_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "client_id is required")
        try:
            items = self.repo.get_sent_requests(client_id)
            logger.debug("Fetched sent requests: client=%s count=%s", client_id, len(items) if items else 0)
            return items
        except PyMongoError:
            logger.exception("Mongo error fetching sent requests: client=%s", client_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to fetch sent requests")

    def get_received_requests(self, freelancer_id: str):
        if not freelancer_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "freelancer_id is required")
        try:
            items = self.repo.get_received_requests(freelancer_id)
            logger.debug("Fetched received requests: freelancer=%s count=%s", freelancer_id, len(items) if items else 0)
            return items
        except PyMongoError:
            logger.exception("Mongo error fetching received requests: freelancer=%s", freelancer_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to fetch received requests")

    def get_total_request_count(self, client_id: str, project_id: str) -> int:
        """Get number of PENDING requests sent by a client for a specific project"""
        if not client_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "client_id is required")
        if not project_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "project_id is required")
        try:
            count = self.repo.count_pending_requests_by_client_and_project(client_id, project_id)
            logger.debug("Fetched pending request count: client=%s project=%s count=%s", client_id, project_id, count)
            return count
        except PyMongoError:
            logger.exception("Mongo error fetching pending request count: client=%s project=%s", client_id, project_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to fetch request count")

    # ---------- Respond ----------
    def respond_request(self, request_id: str, freelancer_id: str, accept: bool):
        if not request_id or not freelancer_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "request_id and freelancer_id are required")

        try:
            req = self.repo.get_request(request_id)
        except PyMongoError:
            logger.exception("Mongo error fetching request for respond: id=%s", request_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to fetch request")

        if not req:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")
        if req.get("freelancer_id") != freelancer_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to respond to this request")
        if req.get("status") != RequestStatus.PENDING.value:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only pending requests can be accepted/rejected")

        new_status = RequestStatus.ACCEPTED.value if accept else RequestStatus.REJECTED.value
        try:
            updated = self.repo.update_status(request_id, new_status, freelancer_id)
            logger.info("Request responded: id=%s freelancer=%s status=%s", request_id, freelancer_id, new_status)
            
            # Send notification to client about acceptance/rejection
            try:
                from app.services.notification import NotificationService
                notification_service = NotificationService()
                
                client_id = req.get("client_id")
                freelancer_name = req.get("freelancer_name", "Freelancer")
                project_title = req.get("project_title", "Project")
                project_id = req.get("project_id")
                
                if accept:
                    notification_service.notify_request_accepted(
                        client_id=client_id,
                        freelancer_name=freelancer_name,
                        project_title=project_title,
                        request_id=request_id,
                        project_id=project_id
                    )
                    logger.info("Notification sent to client: %s for accepted request: %s", client_id, request_id)
                else:
                    notification_service.notify_request_rejected(
                        client_id=client_id,
                        freelancer_name=freelancer_name,
                        project_title=project_title,
                        request_id=request_id,
                        project_id=project_id
                    )
                    logger.info("Notification sent to client: %s for rejected request: %s", client_id, request_id)
            except Exception as e:
                logger.warning("Failed to send request response notification (request still updated): %s", e)
                # Don't fail the request update if notification fails
            
            return updated
        except PyMongoError:
            logger.exception("Mongo error updating request status: id=%s", request_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to update request status")
        
     # ---------- Cancel ----------
    def cancel_request(self, request_id: str, client_id: str) -> Dict[str, Any]:
        if not request_id or not client_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "request_id and client_id are required")

        try:
            req = self.repo.get_request(request_id)
        except PyMongoError:
            logger.exception("Mongo error fetching request for cancel: id=%s", request_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to fetch request")

        if not req:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")
        if req.get("client_id") != client_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to cancel this request")
        if req.get("status") != RequestStatus.PENDING.value:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only pending requests can be cancelled")

        try:
            updated = self.repo.update_status(request_id, RequestStatus.CANCELLED.value, client_id)
            logger.info("Request cancelled: id=%s by client=%s", request_id, client_id)
            return updated
        except PyMongoError:
            logger.exception("Mongo error cancelling request: id=%s", request_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to cancel request")
        
    def cancel_request_by_parties(self, project_id: str, freelancer_id: str, client_id: str, performed_by: str) -> Dict[str, Any]:
        """
        Cancel a request by the combination of project_id, freelancer_id and client_id.

        Expects repo.find_request_by_parties(project_id, freelancer_id, client_id) to return the
        matching request document or None.
        """
        if not project_id or not freelancer_id or not client_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "project_id, freelancer_id and client_id are required")

        try:
            req = self.repo.get_request_by_parties(project_id, freelancer_id, client_id)
        except PyMongoError:
            logger.exception(
                "Mongo error fetching request for cancel by parties: project=%s freelancer=%s client=%s",
                project_id, freelancer_id, client_id
            )
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to fetch request")

        if not req:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found for given parties")

        # permission check: only client (owner) or admin/system actor should cancel — adapt as needed
        if req.get("client_id") != performed_by:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to cancel this request")

        # only allow cancelling pending requests
        if req.get("status") != RequestStatus.PENDING.value:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only pending requests can be cancelled")

        request_id = req.get("request_id")
        if not request_id:
            logger.error(
                "Request found for parties but missing request id: project=%s freelancer=%s client=%s",
                project_id, freelancer_id, client_id
            )
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Invalid request data")

        try:
            updated = self.repo.update_status(request_id, RequestStatus.CANCELLED.value, performed_by)
            logger.info(
                "Request cancelled by parties: request_id=%s project=%s freelancer=%s client=%s performed_by=%s",
                request_id, project_id, freelancer_id, client_id, performed_by
            )
            return updated
        except PyMongoError:
            logger.exception(
                "Mongo error cancelling request by parties: request_id=%s project=%s freelancer=%s client=%s",
                request_id, project_id, freelancer_id, client_id
            )
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to cancel request")

    # ---------- Utilities ----------
    def request_exists(self, client_id: str, freelancer_id: str, project_id: str) -> bool:
        if not client_id or not freelancer_id or not project_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "client_id, freelancer_id, and project_id are required")
        try:
            return self.repo.request_exists(client_id, freelancer_id, project_id)
        except PyMongoError:
            logger.exception("Mongo error checking request existence: client=%s freelancer=%s project=%s", client_id, freelancer_id, project_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to check request existence")
        
    def request_get_one(self, request_id: str) -> Dict[str, Any]:
        if not request_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "request_id is required")
        try:
            req = self.repo.get_request(request_id)
            if not req:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")
            return req
        except PyMongoError:
            logger.exception("Mongo error fetching request: id=%s", request_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to fetch request")
    
    def get_request_by_parties(self, project_id: str, freelancer_id: str, client_id: str) -> Optional[Dict[str, Any]]:
        """Get request by project_id, client_id, and freelancer_id"""
        if not project_id or not freelancer_id or not client_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "project_id, freelancer_id, and client_id are required")
        try:
            request = self.repo.get_request_by_parties(project_id, freelancer_id, client_id)
            return request
        except PyMongoError:
            logger.exception("Mongo error fetching request by parties: project_id=%s client_id=%s freelancer_id=%s", project_id, client_id, freelancer_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to fetch request")

    def project_exists(self, project_id: str, user_id: str, role: str) -> bool:
        if not project_id or not user_id or not role:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "project_id, user_id and role are required")
        if role not in {"CL", "FL", "SA"}:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid role")

        try:
            if role == "CL":
                return self.repo.project_exists(project_id=project_id, client_id=user_id, status=RequestStatus.ACCEPTED.value)
            if role == "FL":
                return self.repo.project_exists(project_id=project_id, freelancer_id=user_id, status=RequestStatus.ACCEPTED.value)
            # SA (super admin) can access all projects by policy
            return True
        except PyMongoError:
            logger.exception("Mongo error checking project existence: project_id=%s user_id=%s role=%s", project_id, user_id, role)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to check project existence")
