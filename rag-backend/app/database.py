import logging
import os
from typing import Optional

from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import OperationFailure

logger = logging.getLogger(__name__)

# Supports both:
#   Local dev  : mongodb://localhost:27017
#   Atlas      : mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority
# Set MONGODB_URI (Atlas style) or fall back to MONGO_URI (legacy).
MONGO_URI = (
    os.getenv("MONGODB_URI")        # Atlas / production
    or os.getenv("MONGO_URI")       # legacy env var name
    or "mongodb://localhost:27017"  # local dev fallback
)
DB_NAME = os.getenv("MONGO_DB_NAME", "leta_history")


def _ensure_optional_unique_index(collection, field: str) -> None:
    """Ensure unique indexes ignore null/missing optional identity fields."""
    index_name = f"{field}_1"
    indexes = collection.index_information()
    existing = indexes.get(index_name)

    if existing:
        is_unique = existing.get("unique") is True
        is_optional = (
            existing.get("sparse") is True
            or "partialFilterExpression" in existing
        )
        if is_unique and is_optional:
            return
        collection.drop_index(index_name)

    collection.create_index(
        [(field, ASCENDING)],
        unique=True,
        partialFilterExpression={field: {"$type": "string"}},
        name=index_name,
    )


def _ensure_indexes(db) -> None:
    """
    Creates indexes on first connect (idempotent — MongoDB ignores duplicates).
    Without these, template search and session lookup are O(n) collection scans.
    """
    try:
        # users: fast login lookup by email or phone
        _ensure_optional_unique_index(db["users"], "email")
        _ensure_optional_unique_index(db["users"], "phone")

        # sessions: fetch all sessions for a user quickly
        db["sessions"].create_index([("user_id", ASCENDING)])
        db["sessions"].create_index([("session_id", ASCENDING)], unique=True)
        db["sessions"].create_index([("updated_at", DESCENDING)])
        # sessions: auto-expire sessions inactive for 90 days
        db["sessions"].create_index(
            [("updated_at", ASCENDING)],
            expireAfterSeconds=90 * 24 * 3600,
            name="sessions_ttl",
        )

        # templates: domain + tag filtering (Netflix-style browse)
        db["templates"].create_index([("domain", ASCENDING), ("tags", ASCENDING)])
        db["templates"].create_index([("title", ASCENDING)])

        # otp_store: TTL index — MongoDB auto-deletes expired OTPs
        db["otp_store"].create_index(
            [("expires_at", ASCENDING)],
            expireAfterSeconds=0,   # delete at the document's own expires_at
        )
        db["otp_store"].create_index([("contact", ASCENDING)], unique=True)

        # feedback: analytics queries by rating and timestamp
        db["feedback"].create_index([("rating", ASCENDING), ("timestamp", DESCENDING)])

        # activity_logs: analytics, auditing, debugging, and training traces
        db["activity_logs"].create_index([("timestamp", DESCENDING)])
        db["activity_logs"].create_index([("user_id", ASCENDING)])
        db["activity_logs"].create_index([("action", ASCENDING)])
        db["activity_logs"].create_index([("category", ASCENDING)])

        # ai_query_analytics: analytics for AI requests
        db["ai_query_analytics"].create_index([("timestamp", DESCENDING)])
        db["ai_query_analytics"].create_index([("user_id", ASCENDING)])
        db["ai_query_analytics"].create_index([("draft_type", ASCENDING)])
        db["ai_query_analytics"].create_index([("model_used", ASCENDING)])
        db["ai_query_analytics"].create_index([("success", ASCENDING)])
        db["ai_query_analytics"].create_index([("user_id", ASCENDING), ("timestamp", DESCENDING)])
        db["ai_query_analytics"].create_index([("success", ASCENDING), ("timestamp", DESCENDING)])
        db["ai_query_analytics"].create_index([("draft_type", ASCENDING), ("timestamp", DESCENDING)])
        db["ai_query_analytics"].create_index([("model_used", ASCENDING), ("timestamp", DESCENDING)])
        db["ai_query_analytics"].create_index([("cache_hit", ASCENDING), ("timestamp", DESCENDING)])
        db["ai_query_analytics"].create_index([("query_id", ASCENDING)], unique=True)

        # knowledge_base indexes
        db["knowledge_base"].create_index([("document_id", ASCENDING)], unique=True)
        db["knowledge_base"].create_index([("sha256", ASCENDING)])
        db["knowledge_base"].create_index([("is_active", ASCENDING)])
        db["knowledge_base"].create_index([("category", ASCENDING)])
        db["knowledge_base"].create_index([("uploaded_at", DESCENDING)])
        db["knowledge_base"].create_index([("title", ASCENDING)])

        # knowledge_audit_logs indexes
        db["knowledge_audit_logs"].create_index([("timestamp", DESCENDING)])
        db["knowledge_audit_logs"].create_index([("action", ASCENDING)])
        db["knowledge_audit_logs"].create_index([("user_id", ASCENDING)])

        logger.info("MongoDB indexes ensured")
    except OperationFailure as e:
        # Non-fatal: Atlas free tier may restrict index creation
        logger.warning(f"Index creation warning (non-fatal): {e}")


class Database:
    client: Optional[MongoClient] = None
    db_name: str = DB_NAME

    def connect(self):
        if not self.client:
            # Mask credentials in log output
            safe_uri = MONGO_URI.split("@")[-1] if "@" in MONGO_URI else MONGO_URI
            logger.info(f"Connecting to MongoDB: ...{safe_uri}")
            try:
                self.client = MongoClient(
                    MONGO_URI,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=10000,
                    socketTimeoutMS=30000,
                    minPoolSize=5,
                    maxPoolSize=50,
                    maxIdleTimeMS=45000,
                    tls=MONGO_URI.startswith("mongodb+srv"),
                    retryWrites=True,
                    w="majority",
                )
                self.client.admin.command("ping")
                logger.info("MongoDB connection successful")
                _ensure_indexes(self.client[self.db_name])
            except Exception as e:
                logger.error(f"MongoDB connection failed: {e}")
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

def get_activity_log_collection():
    return db.get_collection("activity_logs")

def get_db():
    if not db.client:
        db.connect()
    if db.client:
        return db.client[db.db_name]
    return None
