import uuid
from typing import List, Optional
from pymongo.collection import Collection
from fastapi import HTTPException
from app.core.db import database
from app.models.request import RequestStatus
from datetime import datetime, timedelta, timezone


class RequestRepository:
    def __init__(self):
        self.collection: Collection = database["chat_requests"]
        self.user = database["user"]  # add this

    def create_request(self, client_id: str, freelancer_id: str, client_first_name: str, client_last_name: str, freelancer_first_name: str, freelancer_last_name: str, project_id: str, project_name: str) -> dict:
        request_id = str(uuid.uuid4())
        doc = {
            "request_id": request_id,
            "client_id": client_id,
            "client_name": f"{client_first_name} {client_last_name}",
            "freelancer_name": f"{freelancer_first_name} {freelancer_last_name}",
            "freelancer_id": freelancer_id,
            "project_id": project_id,
            "project_title": project_name,
            "status": RequestStatus.PENDING.value,
            "created_at": int(datetime.utcnow().timestamp())  # epoch seconds (UTC)
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
            {"$set": {"status": status, "updated_at": int(datetime.utcnow().timestamp())}}
        )
        if result.matched_count == 0:
            raise HTTPException(404, "Request not found.")
        return self.collection.find_one({"request_id": request_id}, {"_id": 0})
    
    def cancel_expired_requests(self) -> int:
        """
        Mark all pending requests older than 24 hours as 'cancelled'.
        Returns count of modified docs.
        Call this before listing or in endpoints that need up-to-date states.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=1)
        result = self.collection.update_many(
            {"status": "pending", "created_at": {"$lte": cutoff}},
            {"$set": {"status": "cancelled", "cancelled_at": datetime.now(timezone.utc)}}
        )
        return result.modified_count

    

    def get_sent_requests(self, client_id: str) -> list:
        print("Fetching sent requests for client:", client_id)
        cancelled_count = self.cancel_expired_requests()
        print(f"Cancelled {cancelled_count} expired requests.")
        print(self.user.name)
        pipeline = [
            {"$match": {"client_id": client_id, "status": {"$in": [RequestStatus.PENDING.value, RequestStatus.ACCEPTED.value]}}},
            {
                "$lookup": {
                    "from": self.user.name,
                    "localField": "client_id",
                    "foreignField": "user_id",
                    "as": "client_info",
                }
            },
            {
                "$lookup": {
                    "from": self.user.name,
                    "localField": "freelancer_id",
                    "foreignField": "user_id",
                    "as": "freelancer_info",
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "request_id": 1,
                    "project_id": 1,
                    "freelancer_name": 1,
                    "client_name": 1,
                    "client_id": 1,
                    "freelancer_id": 1,
                    "status": 1,
                    "created_at": 1,
                    "subject": 1,
                    "description": 1,
                    "project_title": 1,
                    # include profile pics
                    "client_profile_pic": {"$arrayElemAt": ["$client_info.profile_pic", 0]},
                    "freelancer_profile_pic": {"$arrayElemAt": ["$freelancer_info.profile_pic", 0]},
                }
            },
        ]
        data = list(self.collection.aggregate(pipeline))
        print("Fetched profile pics for sent requests:", data)
        return data
        #        return list(self.collection.aggregate(pipeline))

    def get_received_requests(self, freelancer_id: str) -> list:
        pipeline = [
            {"$match": {"freelancer_id": freelancer_id}},
            {
                "$lookup": {
                    "from": self.user.name,
                    "localField": "client_id",
                    "foreignField": "user_id",
                    "as": "client_info",
                }
            },
            {
                "$lookup": {
                    "from": self.user.name,
                    "localField": "freelancer_id",
                    "foreignField": "user_id",
                    "as": "freelancer_info",
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "request_id": 1,
                    "project_id": 1,
                    "freelancer_name": 1,
                    "client_name": 1,
                    "client_id": 1,
                    "freelancer_id": 1,
                    "status": 1,
                    "created_at": 1,
                    "subject": 1,
                    "description": 1,
                    "project_title": 1,
                    "client_profile_pic": {"$arrayElemAt": ["$client_info.profile_pic", 0]},
                    "freelancer_profile_pic": {"$arrayElemAt": ["$freelancer_info.profile_pic", 0]},
                }
            },
        ]
        return list(self.collection.aggregate(pipeline))
    
    def get_request(self, request_id: str) -> Optional[dict]:
        return self.collection.find_one({"request_id": request_id}, {"_id": 0})
    
    def request_exists(self, client_id: str, freelancer_id: str) -> bool:
        return self.collection.count_documents({
            "client_id": client_id,
            "freelancer_id": freelancer_id,
            "status": RequestStatus.PENDING.value
        }) > 0
    
    def count_total_requests_by_client(self, client_id: str) -> int:
        """
        Count total number of *active* requests sent by a client.

        We intentionally exclude requests that have been cancelled or rejected so that
        the client's available quota is freed up again once a request is no longer active.
        """
        return self.collection.count_documents({
            "client_id": client_id,
            "status": {"$in": [RequestStatus.PENDING.value, RequestStatus.ACCEPTED.value]}
        })
    
    def get_request_by_parties(self, project_id: str, freelancer_id: str, client_id: str) -> Optional[dict]:
        return self.collection.find_one({"project_id": project_id, "freelancer_id": freelancer_id, "client_id": client_id}, {"_id": 0})

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
