import uuid
from typing import List, Optional
from pymongo.collection import Collection
from fastapi import HTTPException
from app.core.db import database
from app.models.ticket import TicketStatus, TimelineEntry, TimelineAction

class TicketRepository:
    def __init__(self):
        self.collection: Collection = database["tickets"]

    def create_ticket(self, data: dict) -> dict:
        ticket_id = str(uuid.uuid4())
        data["ticket_id"] = ticket_id
        self.collection.insert_one(data)
        return self.collection.find_one({"ticket_id": ticket_id}, {"_id": 0})

    def update_ticket(self, ticket_id: str, update_data: dict):
        result = self.collection.update_one({"ticket_id": ticket_id}, {"$set": update_data})
        if result.matched_count == 0:
            raise HTTPException(404, "Ticket not found")
        return self.collection.find_one({"ticket_id": ticket_id}, {"_id": 0})

    def add_timeline_entry(self, ticket_id: str, entry: dict):
        self.collection.update_one(
            {"ticket_id": ticket_id},
            {"$push": {"timeline": entry}}
        )

    def get_ticket(self, ticket_id: str) -> Optional[dict]:
        return self.collection.find_one({"ticket_id": ticket_id}, {"_id": 0})

    def get_tickets_by_freelancer(self, freelancer_id: str) -> List[dict]:
        return list(self.collection.find({"freelancer_id": freelancer_id}, {"_id": 0, "timeline": 0}))

    def get_all_tickets(self) -> List[dict]:
        return list(self.collection.find({}, {"_id": 0}))
