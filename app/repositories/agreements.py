# agreements/repository.py
from typing import List, Optional, Dict, Any
from pymongo.database import Database
from pymongo import ReturnDocument
from datetime import datetime
import logging
from app.core.db import database

logger = logging.getLogger(__name__)

class AgreementRepository:
    def __init__(self):
        self.col = database["agreements"]

    def create(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        self.col.insert_one(doc)
        return self.get_by_id(doc["agreement_id"])

    def get_by_id(self, agreement_id: str) -> Optional[Dict[str, Any]]:
        pipeline = [
            {"$match": {"agreement_id": agreement_id}},
            # lookup client user doc
            {"$lookup": {
                "from": "user",
                "localField": "client.user_id",
                "foreignField": "user_id",
                "as": "client_user"
            }},
            {"$unwind": {"path": "$client_user", "preserveNullAndEmptyArrays": True}},
            # lookup freelancer user doc
            {"$lookup": {
                "from": "user",
                "localField": "freelancer.user_id",
                "foreignField": "user_id",
                "as": "freelancer_user"
            }},
            {"$unwind": {"path": "$freelancer_user", "preserveNullAndEmptyArrays": True}},
            # pull profile pic and username into top-level fields
            {"$addFields": {
                "client_profile_pic": "$client_user.profile_pic",
                "freelancer_profile_pic": "$freelancer_user.profile_pic",
                # populate username in client UserRef
                "client.username": "$client_user.username",
                # populate username in freelancer UserRef
                "freelancer.username": "$freelancer_user.username"
            }},
            # lookup active disputes
            {
                "$lookup": {
                    "from": "tickets",
                    "let": {"aid": "$agreement_id"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {"$eq": ["$agreement_id", "$$aid"]},
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
            # remove helper nested docs and _id
            {"$project": {"client_user": 0, "freelancer_user": 0, "active_tickets": 0, "_id": 0}}
        ]
        results = list(self.col.aggregate(pipeline))
        return results[0] if results else None
    
    def get_filtered(self, filter: Dict[str, Any]) -> List[Dict[str, Any]]:
        pipeline = [
            {"$match": filter},
            # lookup client user doc
            {"$lookup": {
                "from": "user",
                "localField": "client.user_id",
                "foreignField": "user_id",
                "as": "client_user"
            }},
            {"$unwind": {"path": "$client_user", "preserveNullAndEmptyArrays": True}},
            # lookup freelancer user doc
            {"$lookup": {
                "from": "user",
                "localField": "freelancer.user_id",
                "foreignField": "user_id",
                "as": "freelancer_user"
            }},
            {"$unwind": {"path": "$freelancer_user", "preserveNullAndEmptyArrays": True}},
            # pull profile pic and username into top-level fields
            {"$addFields": {
                "client_profile_pic": "$client_user.profile_pic",
                "freelancer_profile_pic": "$freelancer_user.profile_pic",
                # populate username in client UserRef
                "client.username": "$client_user.username",
                # populate username in freelancer UserRef
                "freelancer.username": "$freelancer_user.username"
            }},
            # lookup active disputes
            {
                "$lookup": {
                    "from": "tickets",
                    "let": {"aid": "$agreement_id"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {"$eq": ["$agreement_id", "$$aid"]},
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
            # remove helper nested docs and _id if you don't want it returned
            {"$project": {"client_user": 0, "freelancer_user": 0, "active_tickets": 0, "_id": 0}}
        ]
        return list(self.col.aggregate(pipeline))

    def update(self, agreement_id: str, update_fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        update_fields["updated_at"] = datetime.utcnow()
        res = self.col.find_one_and_update(
            {"agreement_id": agreement_id},
            {"$set": update_fields},
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0}
        )
        return res

    def add_milestone(self, agreement_id: str, milestone_id: str) -> Optional[Dict[str, Any]]:
        print("Adding milestone to agreement:", agreement_id, milestone_id)
        res = self.col.find_one_and_update(
            {"agreement_id": agreement_id},
            {"$push": {"milestones": milestone_id}, "$set": {"updated_at": datetime.utcnow()}},
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0}
        )
        print("Updated agreement with new milestone:", res)
        return res

    def set_status(self, agreement_id: str, status: str) -> Optional[Dict[str, Any]]:
        return self.update(agreement_id, {"status": status})
