from typing import Optional
from pymongo.collection import Collection
from typing import Dict, Any
from fastapi import HTTPException
from app.models.user import UserBase, UserCreate, UserUpdate, UserOut
from app.core.db import database
import uuid
from datetime import datetime, timezone, timedelta

# IST is UTC+5:30
IST = timezone(timedelta(hours=5, minutes=30))

class UserRepository:
    def __init__(self):
        self.collection: Collection = database["user"]

    def create_user(self, user_data: UserCreate) -> Optional[dict]:
        # Create Keycloak user
        # keycloak_id = create_user_in_keycloak(user_data)
        # user_data.username = user_data.first_name.lower() + "_" + user_data.last_name.lower()
        user_dict = user_data.model_dump()
        user_dict.pop("passcode", None)

        audit_log = {
            "created_at":  datetime.now(timezone.utc),
            "created_by": "self",
            "updated_at":  datetime.now(timezone.utc),
            "updated_by": "self",
        }
        user_dict["audit_log"] = audit_log
        
        result = self.collection.insert_one(user_dict)
        return self.collection.find_one({"_id": result.inserted_id}, {"_id": 0})

    def _attach_defaults(self, user: Optional[dict]) -> Optional[dict]:
        if user is not None and "email_verified" not in user:
            user["email_verified"] = False
        
        # Convert first_edit_date to IST if it exists (MongoDB stores as UTC)
        if user and "first_edit_date" in user and user["first_edit_date"]:
            first_edit = user["first_edit_date"]
            if isinstance(first_edit, datetime):
                # MongoDB returns UTC, convert to IST
                if first_edit.tzinfo is None:
                    # Naive datetime from MongoDB, assume UTC
                    first_edit = first_edit.replace(tzinfo=timezone.utc).astimezone(IST)
                elif first_edit.tzinfo == timezone.utc:
                    # UTC datetime, convert to IST
                    first_edit = first_edit.astimezone(IST)
                # If already in IST, keep as is
                user["first_edit_date"] = first_edit
        
        return user

    def get_user_by_id(self, user_id: str) -> Optional[dict]:
        # print("Fetching user by ID:", user_id)
        user = self.collection.find_one({"user_id": user_id, "status": {"$in": ["ACTIVE", "BANNED"]}}, {"_id": 0})
        user = self._attach_defaults(user)
        print("Fetched user:", user.get("user_id") if user else None)
        if not user:
            raise HTTPException(404, "User not found")
        
        # Convert first_edit_date to IST if it exists
        if user and "first_edit_date" in user and user["first_edit_date"]:
            first_edit = user["first_edit_date"]
            if isinstance(first_edit, datetime):
                # Convert to IST if it's in UTC or naive
                if first_edit.tzinfo is None:
                    first_edit = first_edit.replace(tzinfo=timezone.utc).astimezone(IST)
                elif first_edit.tzinfo == timezone.utc:
                    first_edit = first_edit.astimezone(IST)
                user["first_edit_date"] = first_edit
        
        return user
    
    def get_user_by_email(self, email: str) -> Optional[dict]:
        """Get user by email address"""
        user = self.collection.find_one({"email": email, "status": {"$in": ["ACTIVE", "BANNED"]}}, {"_id": 0})
        user = self._attach_defaults(user)
        if not user:
            raise HTTPException(404, "User not found")
        return user

    def get_user_by_keycloak_id(self, keycloak_id: str) -> Optional[dict]:
        """Get user by Keycloak user id"""
        user = self.collection.find_one({"keycloak_id": keycloak_id, "status": {"$in": ["ACTIVE", "BANNED"]}}, {"_id": 0})
        user = self._attach_defaults(user)
        if not user:
            raise HTTPException(404, "User not found")
        return user
    
    def get_freelancers(self) -> list[dict]:
        freelancers = self.collection.find({"role": "FL", "status": "ACTIVE"}, {"_id": 0})
        return list(freelancers)
    
    def find_by_role(self, role: str) -> list[dict]:
        """Find all users by role (for matching algorithm)"""
        users = self.collection.find({"role": role}, {"_id": 0})
        return list(users)
    
    def find_by_user_id(self, user_id: str) -> Optional[dict]:
        """Alias for get_user_by_id (for matching algorithm compatibility)"""
        return self.collection.find_one({"user_id": user_id}, {"_id": 0})
    
    def get_all_users(self) -> list[dict]:
        # users = self.collection.find({"status": "ACTIVE"}, {"_id": 0})
        users = self.collection.find({}, {"_id": 0})
        return list(users)

    # def update_user(self, user_id: str, user_data: UserUpdate) -> Optional[dict]:
    #     if not user_data:
    #         raise HTTPException(400, "No data to update")
    #     self.collection.update_one({"user_id": user_id}, {"$set": user_data})
    #     return self.get_user_by_id(user_id)
    
    def update_user(self, user_id: str, update_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:


        update_payload["audit_log.updated_at"] = datetime.now(timezone.utc)
        update_payload["audit_log.updated_by"] = user_id

        # build $set and $unset based on presence of keys and explicit None values
        set_ops = {}
        unset_ops = {}
        for k, v in update_payload.items():
            if v is None:
                unset_ops[k] = ""   # remove fields explicitly set to null
            else:
                set_ops[k] = v

        update_clause = {}
        if set_ops:
            update_clause["$set"] = set_ops
        if unset_ops:
            update_clause["$unset"] = unset_ops

        if not update_clause:
            # nothing to do
            return self.get_user_by_id(user_id)

        result = self.collection.update_one({"user_id": user_id}, update_clause)

        if result.matched_count == 0:
            return None

        # Return fresh document
        return self.get_user_by_id(user_id)
    
    def update_user_skills(self, user_id: str, skills_payload: list) -> dict:
        """
        skills_payload: list of {"skill_id": "...", "level": "basic"}
        """
        
        result = self.collection.update_one(
            {"user_id": user_id},
            {"$set": {"skill_set": skills_payload}}
        )
        print("Update result:", result.raw_result)
        if result.matched_count == 0:
            raise HTTPException(404, "User not found")
        return self.get_user_by_id(user_id)

    def ban_user(self, user_id: str, reason: str) -> dict:
        result = self.collection.update_one(
            {"user_id": user_id},
            {"$set": {"status": "BANNED", "audit_log.updated_at": datetime.now(timezone.utc), "audit_log.updated_by": "system", "ban_reason": reason}}
        )
        if result.matched_count == 0:
            raise HTTPException(404, "User not found.")
        return None
    
    def delete_user(self, user_id: str) -> dict:
        result = self.collection.update_one(
            {"user_id": user_id},
            {"$set": {"status": "DELETED"}}
        )
        print("Delete result:", result.raw_result, result.matched_count)
        if result.matched_count == 0:
            raise HTTPException(404, "User not found.")
        return None
