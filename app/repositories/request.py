import uuid
from typing import List, Optional
from pymongo.collection import Collection
from fastapi import HTTPException
from app.core.db import database
from app.models.request import RequestStatus

class RequestRepository:
    def __init__(self):
        self.collection: Collection = database["chat_requests"]

    def create_request(self, client_id: str, freelancer_id: str) -> dict:
        request_id = str(uuid.uuid4())
        doc = {
            "request_id": request_id,
            "client_id": client_id,
            "freelancer_id": freelancer_id,
            "status": RequestStatus.PENDING.value,
        }
        # Check for existing pending request
        existing = self.collection.find_one({
            "client_id": client_id,
            "freelancer_id": freelancer_id,
            "status": RequestStatus.PENDING.value
        })
        if existing:
            raise HTTPException(400, "Request already exists and is pending.")
        self.collection.insert_one(doc)
        return doc

    def update_status(self, request_id: str, status: str, acting_user_id: str) -> Optional[dict]:
        result = self.collection.update_one(
            {"request_id": request_id},
            {"$set": {"status": status}}
        )
        if result.matched_count == 0:
            raise HTTPException(404, "Request not found.")
        return self.collection.find_one({"request_id": request_id}, {"_id": 0})

    def get_sent_requests(self, client_id: str) -> list:
        return list(self.collection.find({"client_id": client_id}, {"_id": 0}))

    def get_received_requests(self, freelancer_id: str) -> list:
        return list(self.collection.find({"freelancer_id": freelancer_id}, {"_id": 0}))

    def get_request(self, request_id: str) -> Optional[dict]:
        return self.collection.find_one({"request_id": request_id}, {"_id": 0})
    
    def request_exists(self, client_id: str, freelancer_id: str) -> bool:
        return self.collection.count_documents({
            "client_id": client_id,
            "freelancer_id": freelancer_id,
            "status": RequestStatus.PENDING.value
        }) > 0

    def delete_request(self, request_id: str, client_id: str):
        result = self.collection.delete_one({"request_id": request_id, "client_id": client_id})
        if result.deleted_count == 0:
            raise HTTPException(404, "Request not found or unauthorized.")
        
    def project_exists(self, project_id: str, status: str, client_id: str = None, freelancer_id: str = None) -> bool:
        if client_id:
            data = self.collection.count_documents({
                "project_id": project_id,
                "client_id": client_id,
                "status": status
            })
        elif freelancer_id:
            data = self.collection.count_documents({
                "project_id": project_id,
                "freelancer_id": freelancer_id,
                "status": status
            })
        else:
            return False
        if data > 0:
            return True
        return False
