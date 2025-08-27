from typing import Optional
from pymongo.collection import Collection
from fastapi import HTTPException
from app.models.user import UserBase, UserCreate, UserUpdate, UserOut
from app.core.db import database
import uuid

class UserRepository:
    def __init__(self):
        self.collection: Collection = database["user"]

    def create_user(self, user_data: UserCreate) -> Optional[dict]:
        # Create Keycloak user
        # keycloak_id = create_user_in_keycloak(user_data)
        user_dict = user_data.model_dump()
        user_dict.pop("passcode", None)
        
        result = self.collection.insert_one(user_dict)
        return self.collection.find_one({"_id": result.inserted_id}, {"_id": 0})

    def get_user_by_id(self, user_id: str) -> Optional[dict]:
        print("Fetching user by ID:", user_id)
        user = self.collection.find_one({"user_id": user_id, "status": "ACTIVE"}, {"_id": 0})
        if not user:
            raise HTTPException(404, "User not found")
        return user
    
    def get_freelancers(self) -> list[dict]:
        freelancers = self.collection.find({"role": "FL", "status": "ACTIVE"}, {"_id": 0})
        return list(freelancers)

    def update_user(self, user_id: str, user_data: UserUpdate) -> Optional[dict]:
        if not user_data:
            raise HTTPException(400, "No data to update")
        self.collection.update_one({"user_id": user_id}, {"$set": user_data})
        return self.get_user_by_id(user_id)

    def ban_user(self, user_id: str) -> dict:
        result = self.collection.update_one(
            {"user_id": user_id},
            {"$set": {"status": "BANNED"}}
        )
        if result.matched_count == 0:
            raise HTTPException(404, "User not found.")
        return None
    
    def delete_user(self, user_id: str) -> dict:
        result = self.collection.update_one(
            {"user_id": user_id},
            {"$set": {"status": "DELETED"}}
        )
        if result.matched_count == 0:
            raise HTTPException(404, "User not found.")
        return None
