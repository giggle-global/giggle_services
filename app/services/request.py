from app.repositories.request import RequestRepository
from app.repositories.user import UserRepository
from app.models.request import RequestCreate, RequestUpdate, RequestOut, RequestStatus
from fastapi import HTTPException


class RequestService:
    def __init__(self, repo: RequestRepository = None, user_repo: UserRepository = None):
        self.repo = repo or RequestRepository()
        self.user_repo = user_repo or UserRepository()

    def create_request(self, client_id: str, freelancer_id: str):
        client = self.user_repo.get_user_by_id(client_id)
        if not client or client.get("role") != "CL":
            raise HTTPException(400, "Invalid client ID")
        freelancer = self.user_repo.get_user_by_id(freelancer_id)
        if not freelancer or freelancer.get("role") != "FL":
            raise HTTPException(400, "Invalid freelancer ID")
        if client_id == freelancer_id:
            raise HTTPException(400, "Client and freelancer cannot be the same")
        if self.repo.request_exists(client_id, freelancer_id):
            raise HTTPException(400, "Request already exists")
        return self.repo.create_request(client_id, freelancer_id)

    def cancel_request(self, request_id: str, client_id: str):
        # Mark as cancelled
        req = self.repo.get_request(request_id)
        if not req or req["client_id"] != client_id:
            raise HTTPException(403, "Not allowed")
        if req["status"] != RequestStatus.PENDING.value:
            raise HTTPException(400, "Only pending requests can be cancelled")
        return self.repo.update_status(request_id, RequestStatus.CANCELLED.value, client_id)

    def get_sent_requests(self, client_id: str):
        return self.repo.get_sent_requests(client_id)

    def get_received_requests(self, freelancer_id: str):
        return self.repo.get_received_requests(freelancer_id)

    def respond_request(self, request_id: str, freelancer_id: str, accept: bool):
        req = self.repo.get_request(request_id)
        if not req or req["freelancer_id"] != freelancer_id:
            raise HTTPException(403, "Not allowed")
        if req["status"] != RequestStatus.PENDING.value:
            raise HTTPException(400, "Only pending requests can be accepted/rejected")
        new_status = RequestStatus.ACCEPTED.value if accept else RequestStatus.REJECTED.value
        return self.repo.update_status(request_id, new_status, freelancer_id)
    
    def request_exists(self, client_id: str, freelancer_id: str):
        return self.repo.request_exists(client_id, freelancer_id)
    
    def project_exists(self, project_id: str, user_id: str, role: str):
        if role == "CL":
            return self.repo.project_exists(project_id=project_id, client_id=user_id, status=RequestStatus.ACCEPTED.value)
        elif role == "FL":
            # For freelancers, check if they have accepted the project
            return self.repo.project_exists(project_id=project_id, freelancer_id=user_id ,status=RequestStatus.ACCEPTED.value)
        elif role == "SA":
            return True
        return False
