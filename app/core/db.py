# app/db.py
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from app.core.config import config

DATABASE_URL = f"mongodb://{config['db_user']}:{config['db_password']}@{config['db_url']}"
DATABASE_NAME = config["db_name"]

print(f"Connecting to MongoDB at {DATABASE_URL}...")  # Debugging line
client = MongoClient(DATABASE_URL)
database = client[DATABASE_NAME]


def check_db_connection() -> bool:
    """Ping MongoDB to check if the connection is alive."""
    try:
        client.admin.command("ping")  # lightweight command
        print("✅ Successfully connected to MongoDB")
        return True
    except ConnectionFailure as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        return False


def get_audit_collection(collection_name: str):
    return database[f"{collection_name}_audit_log"]


# --- Run check on import (startup) ---
if not check_db_connection():
    # You can choose: either exit app or just warn
    print("⚠️ MongoDB is not reachable. Please check your connection settings.")
