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
            "created_at": int(datetime.now(timezone.utc).timestamp())  # epoch seconds (UTC)
        }
        # Check for existing active request (PENDING or ACCEPTED) for the same client, freelancer, and project
        # REJECTED and CANCELLED requests don't block new requests
        existing = self.collection.find_one({
            "client_id": client_id,
            "freelancer_id": freelancer_id,
            "project_id": project_id,
            "status": {"$in": [RequestStatus.PENDING.value, RequestStatus.ACCEPTED.value]}
        })
        if existing:
            status_msg = "pending" if existing.get("status") == RequestStatus.PENDING.value else "accepted"
            raise HTTPException(400, f"You already have a {status_msg} request to this freelancer for this project.")
        self.collection.insert_one(doc)
        return doc

    def update_status(self, request_id: str, status: str, acting_user_id: str) -> Optional[dict]:
        result = self.collection.update_one(
            {"request_id": request_id},
            {"$set": {"status": status, "updated_at": int(datetime.now(timezone.utc).timestamp())}}
        )
        if result.matched_count == 0:
            raise HTTPException(404, "Request not found.")
        return self.collection.find_one({"request_id": request_id}, {"_id": 0})
    
    def reject_expired_requests(self, hours: float = 12.0) -> int:
        """
        Mark all pending requests older than specified hours as 'rejected'.
        Returns count of modified docs.
        Call this before listing or in endpoints that need up-to-date states.
        
        Args:
            hours: Number of hours after which requests should be rejected (default: 12.0)
        """
        # created_at is stored as epoch seconds (int), so convert cutoff to epoch seconds
        now_utc = datetime.now(timezone.utc)
        cutoff_timestamp = int((now_utc - timedelta(hours=hours)).timestamp())
        
        result = self.collection.update_many(
            {"status": RequestStatus.PENDING.value, "created_at": {"$lte": cutoff_timestamp}},
            {"$set": {"status": RequestStatus.REJECTED.value, "updated_at": int(now_utc.timestamp())}}
        )
        return result.modified_count

    

    def get_sent_requests(self, client_id: str) -> list:
        print("Fetching sent requests for client:", client_id)
        rejected_count = self.reject_expired_requests()
        print(f"Rejected {rejected_count} expired requests.")
        pipeline = [
            {"$match": {"client_id": client_id, "status": {"$in": [RequestStatus.PENDING.value, RequestStatus.ACCEPTED.value, RequestStatus.REJECTED.value]}}},
            {
                "$lookup": {
                    "from": "user",
                    "localField": "client_id",
                    "foreignField": "user_id",
                    "as": "client_info",
                }
            },
            {
                "$lookup": {
                    "from": "user",
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
            {
                "$lookup": {
                    "from": "tickets",
                    "let": {"pid": "$project_id"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {"$eq": ["$project_id", "$$pid"]},
                                "status": {"$in": ["open", "in_progress", "reopened"]}
                            }
                        },
                        {"$sort": {"created_at": 1}},
                        {"$limit": 1}
                    ],
                    "as": "active_tickets"
                }
            },
            {
                "$addFields": {
                    "has_dispute": {"$gt": [{"$size": "$active_tickets"}, 0]},
                    "dispute_timestamp": {
                        "$cond": {
                            "if": {"$gt": [{"$size": "$active_tickets"}, 0]},
                            "then": {"$arrayElemAt": [{"$arrayElemAt": ["$active_tickets.timeline.timestamp", 0]}, 0]},
                            "else": None
                        }
                    },
                    "ticket_id": {
                        "$cond": {
                            "if": {"$gt": [{"$size": "$active_tickets"}, 0]},
                            "then": {"$arrayElemAt": ["$active_tickets.ticket_id", 0]},
                            "else": None
                        }
                    }
                }
            },
            {
                "$project": {
                    "active_tickets": 0
                }
            }
        ]
        data = list(self.collection.aggregate(pipeline))
        print("Fetched profile pics for sent requests:", data)
        return data

    def get_received_requests(self, freelancer_id: str) -> list:
        # Reject expired requests before fetching
        self.reject_expired_requests()
        pipeline = [
            {"$match": {"freelancer_id": freelancer_id}},
            {
                "$lookup": {
                    "from": "user",
                    "localField": "client_id",
                    "foreignField": "user_id",
                    "as": "client_info",
                }
            },
            {
                "$lookup": {
                    "from": "user",
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
            {
                "$lookup": {
                    "from": "tickets",
                    "let": {"pid": "$project_id"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {"$eq": ["$project_id", "$$pid"]},
                                "status": {"$in": ["open", "in_progress", "reopened"]}
                            }
                        },
                        {"$sort": {"created_at": 1}},
                        {"$limit": 1}
                    ],
                    "as": "active_tickets"
                }
            },
            {
                "$addFields": {
                    "has_dispute": {"$gt": [{"$size": "$active_tickets"}, 0]},
                    "dispute_timestamp": {
                        "$cond": {
                            "if": {"$gt": [{"$size": "$active_tickets"}, 0]},
                            "then": {"$arrayElemAt": [{"$arrayElemAt": ["$active_tickets.timeline.timestamp", 0]}, 0]},
                            "else": None
                        }
                    },
                    "ticket_id": {
                        "$cond": {
                            "if": {"$gt": [{"$size": "$active_tickets"}, 0]},
                            "then": {"$arrayElemAt": ["$active_tickets.ticket_id", 0]},
                            "else": None
                        }
                    }
                }
            },
            {
                "$project": {
                    "active_tickets": 0
                }
            }
        ]
        return list(self.collection.aggregate(pipeline))
    
    def get_request(self, request_id: str) -> Optional[dict]:
        return self.collection.find_one({"request_id": request_id}, {"_id": 0})
    
    def request_exists(self, client_id: str, freelancer_id: str, project_id: str) -> bool:
        """
        Check if an active request (PENDING or ACCEPTED) already exists for the same client, freelancer, and project.
        REJECTED and CANCELLED requests don't block new requests.
        """
        return self.collection.count_documents({
            "client_id": client_id,
            "freelancer_id": freelancer_id,
            "project_id": project_id,
            "status": {"$in": [RequestStatus.PENDING.value, RequestStatus.ACCEPTED.value]}
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
    
    def count_pending_requests_by_client_and_project(self, client_id: str, project_id: str) -> int:
        """
        Count number of PENDING requests sent by a client for a specific project.
        
        Only PENDING requests count toward the limit. When a request is ACCEPTED or REJECTED,
        it's no longer PENDING, so the count automatically reduces.
        """
        return self.collection.count_documents({
            "client_id": client_id,
            "project_id": project_id,
            "status": RequestStatus.PENDING.value
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
