"""
MongoDB connection manager.

Handles checking MongoDB availability on startup
and establishing connections.
"""

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from src.config.config import settings

class MongoDBManager:
    """Manages connection and checks for MongoDB."""

    def __init__(self) -> None:
        self.client: MongoClient | None = None
        self.db = None

    def connect(self) -> None:
        """
        Connects to MongoDB and verifies the connection with a ping.
        Raises ConnectionError if the database is unreachable.
        """
        try:
            # Set serverSelectionTimeoutMS to 3000ms for fast failing
            self.client = MongoClient(
                settings.MONGODB_URI,
                serverSelectionTimeoutMS=3000
            )
            # Verify connectivity
            self.client.admin.command("ping")
            self.db = self.client[settings.MONGODB_DATABASE]
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            self.client = None
            self.db = None
            raise ConnectionError(
                "MongoDB not running. Please start MongoDB or configure MongoDB Atlas."
            ) from e

    def get_db(self):
        """Returns the database instance. Connects if not already connected."""
        if self.db is None:
            self.connect()
        return self.db

# Global manager instance
db_manager = MongoDBManager()
