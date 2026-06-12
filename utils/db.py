from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "hrms_db")

# Single client instance reused across requests
client: AsyncIOMotorClient = None
db = None


async def connect_db():
    """Connect to MongoDB. Called on app startup."""
    global client, db
    try:
        client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        # Ping to confirm connection works
        await client.admin.command("ping")
        db = client[MONGO_DB_NAME]
        print(f"MongoDB connected -> {MONGO_DB_NAME}")
    except ConnectionFailure as e:
        print(f"MongoDB connection failed: {e}")
        raise


async def close_db():
    """Close MongoDB connection. Called on app shutdown."""
    global client
    if client:
        client.close()
        print("MongoDB connection closed")


def get_db():
    """Return the active database instance."""
    return db


def get_collection(name: str):
    """Return a named collection from the active database."""
    return db[name]
