from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import HTTPException
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "hrms_db")

# Single client instance reused across requests
client: AsyncIOMotorClient = None
db = None


async def connect_db():
    """Initialise the MongoDB client without blocking startup.

    The client is created immediately and the database handle is assigned so
    that request handlers can use them straight away.  No network I/O is
    performed here — Motor establishes the actual connection lazily on the
    first operation, so a slow or temporarily-unavailable Atlas cluster will
    never prevent the app from accepting requests.
    """
    global client, db
    try:
        client = AsyncIOMotorClient(
            MONGO_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
        )
        db = client[MONGO_DB_NAME]
        print(f"MongoDB client initialised -> {MONGO_DB_NAME}")
    except Exception as e:
        # Log the problem but do NOT re-raise — the app must still start so
        # that the health-check endpoint and other routes remain reachable.
        print(f"MongoDB client initialisation error (non-fatal): {e}")


async def close_db():
    """Close MongoDB connection. Called on app shutdown."""
    global client
    if client:
        client.close()
        print("MongoDB connection closed")


def get_db():
    """Return the active database instance.

    Raises HTTP 503 if the client was never successfully initialised so that
    callers receive a clear error instead of an unhandled AttributeError.
    """
    if db is None:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable — MongoDB client is not initialised.",
        )
    return db


def get_collection(name: str):
    """Return a named collection from the active database.

    Raises HTTP 503 if the client was never successfully initialised.
    """
    if db is None:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable — MongoDB client is not initialised.",
        )
    return db[name]
