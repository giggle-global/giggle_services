# app/repositories/review.py
import uuid
import time
from typing import List, Optional
from pymongo.collection import Collection
from fastapi import HTTPException
from app.core.db import database
from app.models.review import ReviewCreate

class ReviewRepository:
    def __init__(self):
        self.collection: Collection = database["reviews"]
        # Create indexes if needed
        try:
            self.collection.create_index("review_id", unique=True)
            self.collection.create_index([("freelancer_id", 1), ("created_at", -1)])
            self.collection.create_index("client_id")
        except Exception:
            pass

    def now_epoch(self) -> int:
        return int(time.time())

    def create_review(self, payload: ReviewCreate) -> dict:
        review_id = str(uuid.uuid4())
        now = self.now_epoch()
        doc = payload.model_dump()
        doc.update({
            "review_id": review_id,
            "created_at": now,
            "updated_at": None
        })
        try:
            self.collection.insert_one(doc)
        except Exception as e:
            raise HTTPException(status_code=500, detail="Failed to create review")
        # return without _id
        return self.collection.find_one({"review_id": review_id}, {"_id": 0})

    def update_review(self, review_id: str, update_data: dict, client_id: str) -> dict:
        if not update_data:
            raise HTTPException(status_code=400, detail="No data to update")
        now = self.now_epoch()
        res = self.collection.find_one_and_update(
            {"review_id": review_id, "client_id": client_id},
            {"$set": {**update_data, "updated_at": now}},
            projection={"_id": 0},
            return_document=True
        )
        if not res:
            raise HTTPException(status_code=404, detail="Review not found or not owned by client")
        return res

    def delete_review(self, review_id: str, client_id: str) -> None:
        res = self.collection.delete_one({"review_id": review_id, "client_id": client_id})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Review not found or not owned by client")

    def get_review(self, review_id: str) -> Optional[dict]:
        return self.collection.find_one({"review_id": review_id}, {"_id": 0})

    # def list_reviews_for_freelancer(self, freelancer_id: str, limit: int = 50, skip: int = 0) -> List[dict]:
    #     return list(self.collection.find({"freelancer_id": freelancer_id}, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit))

    # def list_reviews_by_client(self, client_id: str, limit: int = 50, skip: int = 0) -> List[dict]:
    #     return list(self.collection.find({"client_id": client_id}, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit))

    def list_reviews_for_freelancer(self, freelancer_id: str, limit: int = 50, skip: int = 0) -> List[dict]:
        pipeline = [
            {"$match": {"freelancer_id": freelancer_id}},
            # {"$sort": {"created_at": -1}},
            # {"$skip": skip},
            # {"$limit": limit},
            # Lookup client details
            {"$lookup": {
                "from": "user",
                "localField": "client_id",
                "foreignField": "user_id",
                "as": "client_info"
            }},
            {"$unwind": {"path": "$client_info", "preserveNullAndEmptyArrays": True}},
            {"$project": {
                "_id": 0,
                "review_id": 1,
                "freelancer_id": 1,
                "client_id": 1,
                "stars": 1,
                "comment": 1,
                "created_at": 1,
                "updated_at": 1,
                "client_first_name": "$client_info.first_name",
                "client_last_name": "$client_info.last_name",
                "client_avatar_url": "$client_info.profile_pic"
            }}
        ]
        print("check pipeline: ",pipeline)
        return list(self.collection.aggregate(pipeline))

    def list_reviews_by_client(self, client_id: str, limit: int = 50, skip: int = 0) -> List[dict]:
        pipeline = [
            {"$match": {"client_id": client_id}},
            {"$sort": {"created_at": -1}},
            {"$skip": skip},
            {"$limit": limit},
            # Lookup freelancer details
            {"$lookup": {
                "from": "user",
                "localField": "freelancer_id",
                "foreignField": "user_id",
                "as": "freelancer_info"
            }},
            {"$unwind": {"path": "$freelancer_info", "preserveNullAndEmptyArrays": True}},
            {"$project": {
                "_id": 0,
                "review_id": 1,
                "freelancer_id": 1,
                "client_id": 1,
                "stars": 1,
                "comment": 1,
                "created_at": 1,
                "updated_at": 1,
                "client_company_name": 1,
                "gig_title": 1,
                "freelancer_first_name": "$freelancer_info.first_name",
                "freelancer_last_name": "$freelancer_info.last_name",
                "freelancer_avatar_url": "$freelancer_info.profile_pic"
            }}
        ]
        return list(self.collection.aggregate(pipeline))


    def average_rating_for_freelancer(self, type: str, user_id: str) -> float:
        if type == "client":
            pipeline = [
                {"$match": {"client_id": user_id}},
                {"$group": {"_id": "$client_id", "avg": {"$avg": "$stars"}, "count": {"$sum": 1}}}
            ]
        else:
            pipeline = [
                {"$match": {"freelancer_id": user_id}},
                {"$group": {"_id": "$freelancer_id", "avg": {"$avg": "$stars"}, "count": {"$sum": 1}}}
            ]
        res = list(self.collection.aggregate(pipeline))
        if not res:
            return 0.0
        return float(res[0]["avg"])
