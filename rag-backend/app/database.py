from pymongo import MongoClient
import os
from typing import Optional

# Configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB_NAME", "leta_history")

class Database:
    client: Optional[MongoClient] = None
    db_name: str = DB_NAME

    def connect(self):
        if not self.client:
            print(f"Connecting to MongoDB at {MONGO_URI}...")
            try:
                self.client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
                # Quick health check
                self.client.admin.command('ping')
                print("MongoDB Connection Successful.")
            except Exception as e:
                print(f"MongoDB Connection Failed: {e}")
                self.client = None

    def get_collection(self, collection_name: str):
        if not self.client:
            self.connect()
        
        if self.client:
            return self.client[self.db_name][collection_name]
        return None

db = Database()

def get_session_collection():
    return db.get_collection("sessions")

def get_user_collection():
    return db.get_collection("users")

def get_template_collection():
    return db.get_collection("templates")

def get_otp_collection():
    return db.get_collection("otp_store")

def get_db():
    if not db.client:
        db.connect()
    if db.client:
        return db.client[db.db_name]
    return None
