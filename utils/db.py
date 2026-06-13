from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import HTTPException
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "hrms_db")

# Single client instance reused across requests — initialised lazily on first use
client: AsyncIOMotorClient = None
db = None


def _ensure_client():
    """Create the Motor client and database handle if not already done.

    This is intentionally synchronous and side-effect-free with respect to
    the network: AsyncIOMotorClient does NOT open any sockets or perform DNS
    resolution at construction time.  All real I/O happens on the first
    actual database operation, so calling this function never blocks.
    """
    global client, db
    if client is None:
        client = AsyncIOMotorClient(
            MONGO_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
        )
        db = client[MONGO_DB_NAME]
        print(f"MongoDB client initialised (lazy) -> {MONGO_DB_NAME}")


async def close_db():
    """Close MongoDB connection. Called on app shutdown."""
    global client, db
    if client:
        client.close()
        client = None
        db = None
        print("MongoDB connection closed")


def get_db():
    """Return the active database instance, initialising the client lazily.

    The client is created on the first call to this function — never during
    app startup — so a slow or temporarily-unavailable Atlas cluster will
    never prevent the app from accepting requests.
    """
    _ensure_client()
    return db


def get_collection(name: str):
    """Return a named collection from the active database.

    The client is created on the first call to this function if it has not
    been initialised yet.
    """
    _ensure_client()
    return db[name]
