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
        tickets = list(self.collection.find({"freelancer_id": freelancer_id}, {"_id": 0}))
        # Set timeline to None if excluded, or ensure it's a list
        for ticket in tickets:
            if "timeline" not in ticket:
                ticket["timeline"] = None
            elif ticket.get("timeline") is None:
                ticket["timeline"] = None
        return tickets
    
    def get_tickets_by_client(self, client_id: str) -> List[dict]:
        """Get all tickets where the client is involved"""
        tickets = list(self.collection.find({"client_id": client_id}, {"_id": 0}))
        # Set timeline to None if excluded, or ensure it's a list
        for ticket in tickets:
            if "timeline" not in ticket:
                ticket["timeline"] = None
            elif ticket.get("timeline") is None:
                ticket["timeline"] = None
        return tickets

    def get_all_tickets(self) -> List[dict]:
        tickets = list(self.collection.find({}, {"_id": 0}))
        # Set timeline to None if excluded, or ensure it's a list
        for ticket in tickets:
            if "timeline" not in ticket:
                ticket["timeline"] = None
            elif ticket.get("timeline") is None:
                ticket["timeline"] = None
        return tickets
    
    def get_tickets_by_project_id(self, project_id: str) -> List[dict]:
        """Get all tickets (disputes) for a specific project_id"""
        return list(self.collection.find({"project_id": project_id}, {"_id": 0}))
    
    def has_active_dispute(self, project_id: str) -> bool:
        """Check if there's an active dispute (open/in_progress/reopened) for a project"""
        active_statuses = ["open", "in_progress", "reopened"]
        count = self.collection.count_documents({
            "project_id": project_id,
            "status": {"$in": active_statuses}
        })
        return count > 0