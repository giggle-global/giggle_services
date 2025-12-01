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

# Maximum number of requests a client can send overall
MAX_REQUESTS_PER_CLIENT = 10


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

        # Check total request limit (10 requests overall per client)
        try:
            total_requests = self.repo.count_total_requests_by_client(client_id)
            if total_requests >= MAX_REQUESTS_PER_CLIENT:
                logger.warning("Request limit exceeded: client=%s total_requests=%s", client_id, total_requests)
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"You have reached the maximum limit of {MAX_REQUESTS_PER_CLIENT} requests. You cannot send more requests."
                )
        except PyMongoError:
            logger.exception("Mongo error checking total requests: client=%s", client_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to verify request limit")

        try:
            if self.repo.request_exists(client_id, freelancer_id):
                logger.info("Duplicate request prevented: client=%s freelancer=%s", client_id, freelancer_id)
                raise HTTPException(status.HTTP_409_CONFLICT, "Request already exists")
        except PyMongoError:
            logger.exception("Mongo error checking existing request: client=%s freelancer=%s", client_id, freelancer_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to verify request existence")

        try:
            created = self.repo.create_request(client_id, freelancer_id, client.get("first_name"), client.get("last_name"), freelancer.get("first_name"), freelancer.get("last_name"), project_id, project_name=project_details.get("title"))
            logger.info("Request created: id=%s client=%s freelancer=%s", getattr(created, "id", None), client_id, freelancer_id)
            
            # Send notification to freelancer
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

    def get_total_request_count(self, client_id: str) -> int:
        """Get total number of requests sent by a client (all statuses)"""
        if not client_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "client_id is required")
        try:
            count = self.repo.count_total_requests_by_client(client_id)
            logger.debug("Fetched total request count: client=%s count=%s", client_id, count)
            return count
        except PyMongoError:
            logger.exception("Mongo error fetching total request count: client=%s", client_id)
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
    def request_exists(self, client_id: str, freelancer_id: str) -> bool:
        if not client_id or not freelancer_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "client_id and freelancer_id are required")
        try:
            return self.repo.request_exists(client_id, freelancer_id)
        except PyMongoError:
            logger.exception("Mongo error checking request existence: client=%s freelancer=%s", client_id, freelancer_id)
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
