from app.repositories.request import RequestRepository
from app.models.request import RequestCreate, RequestUpdate, RequestOut, RequestStatus
from fastapi import HTTPException

class RequestService:
    def __init__(self, repo: RequestRepository = None):
        self.repo = repo or RequestRepository()

    def create_request(self, client_id: str, freelancer_id: str):
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
