# app/db.py
from pymongo import MongoClient
from app.core.config import config


DATABASE_URL = f"mongodb://{config['db_user']}:{config['db_password']}@{config['db_url']}"
DATABASE_NAME = config["db_name"]

print(f"Connecting to MongoDB at {DATABASE_URL}...")  # Debugging line
client = MongoClient(DATABASE_URL)
database = client[DATABASE_NAME]

def get_audit_collection(collection_name:str):
    return database[f"{collection_name}_audit_log"]