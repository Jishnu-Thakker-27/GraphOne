"""
MongoDB connection manager.

Handles checking MongoDB availability on startup,
establishing connections, and provides a persistent mock database fallback if MongoDB is offline.
"""

import os
import json
import copy
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from loguru import logger
from src.config.config import settings

# =========================================================================
# Mock MongoDB Implementation for Offline Fallback (File-Persisted)
# =========================================================================

MOCK_DB_FILE = os.path.join("outputs", "mock_mongodb.json")

def _deserialize_dates(doc: Any) -> Any:
    """Helper to recursively parse ISO strings back to UTC datetime objects."""
    if isinstance(doc, dict):
        return {k: _deserialize_dates(v) for k, v in doc.items()}
    elif isinstance(doc, list):
        return [_deserialize_dates(x) for x in doc]
    elif isinstance(doc, str):
        # Match ISO-8601 timestamp patterns: e.g., '2026-07-19T10:00:00'
        import re
        if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", doc):
            from src.utils.date_normalizer import DateNormalizer
            dt = DateNormalizer.normalize(doc)
            if dt:
                return dt
    return doc

class MockCursor:
    """Mock PyMongo Cursor to support sort, limit, and iteration."""
    def __init__(self, data: List[Dict[str, Any]]) -> None:
        self.data = data

    def sort(self, *args, **kwargs) -> "MockCursor":
        return self

    def limit(self, limit_val: int) -> "MockCursor":
        if limit_val > 0:
            self.data = self.data[:limit_val]
        return self

    def __iter__(self):
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)

class MockCollection:
    """Mock PyMongo Collection to handle basic operations in-memory and write to disk."""
    def __init__(self, name: str, db_file: str) -> None:
        self.name = name
        self.db_file = db_file
        self.data: Dict[str, Dict[str, Any]] = {}
        self._load_data()

    def _load_data(self) -> None:
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, "r", encoding="utf-8") as f:
                    full_db = json.load(f)
                    self.data = _deserialize_dates(full_db.get(self.name, {}))
            except Exception as e:
                logger.warning(f"Failed to load mock DB from file: {e}")

    def _save_data(self) -> None:
        full_db = {}
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, "r", encoding="utf-8") as f:
                    full_db = json.load(f)
            except Exception:
                pass
        
        # Serialize python datetimes to strings inside the JSON representation
        full_db[self.name] = self.data
        try:
            os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
            with open(self.db_file, "w", encoding="utf-8") as f:
                json.dump(full_db, f, default=str, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save mock DB file: {e}")

    def insert_one(self, document: Dict[str, Any]) -> Any:
        doc = copy.deepcopy(document)
        if "_id" not in doc:
            doc["_id"] = str(uuid.uuid4())
        self.data[str(doc["_id"])] = doc
        self._save_data()

        class InsertResult:
            inserted_id = doc["_id"]
        return InsertResult()

    def _match(self, doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
        """Simple query matching for nested dictionary keys (e.g. 'content.entityName')."""
        for qk, qv in query.items():
            parts = qk.split(".")
            val = doc
            for p in parts:
                if isinstance(val, dict):
                    val = val.get(p)
                else:
                    val = None
                    break
            
            # Normalize comparison values (string comparison for datetimes vs ISO strings)
            if isinstance(val, datetime) and isinstance(qv, str):
                from src.utils.date_normalizer import DateNormalizer
                dt_qv = DateNormalizer.normalize(qv)
                if val != dt_qv:
                    return False
            elif val != qv:
                return False
        return True

    def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        results = self.find(query)
        return list(results)[0] if len(results) > 0 else None

    def find(self, query: Optional[Dict[str, Any]] = None) -> MockCursor:
        query = query or {}
        results = []
        for doc in self.data.values():
            if self._match(doc, query):
                results.append(copy.deepcopy(doc))
        return MockCursor(results)

    def update_one(self, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = False) -> Any:
        matched_id = None
        for doc_id, doc in self.data.items():
            if self._match(doc, query):
                matched_id = doc_id
                break

        class UpdateResult:
            modified_count = 0

        set_ops = update.get("$set", {})

        if matched_id:
            doc = self.data[matched_id]
            for sk, sv in set_ops.items():
                parts = sk.split(".")
                d = doc
                for p in parts[:-1]:
                    if p not in d:
                        d[p] = {}
                    d = d[p]
                d[parts[-1]] = copy.deepcopy(sv)
            self._save_data()
            res = UpdateResult()
            res.modified_count = 1
            return res
        elif upsert:
            new_doc: Dict[str, Any] = {}
            for qk, qv in query.items():
                if "$" not in qk:
                    parts = qk.split(".")
                    d = new_doc
                    for p in parts[:-1]:
                        if p not in d:
                            d[p] = {}
                        d = d[p]
                    d[parts[-1]] = copy.deepcopy(qv)
            for sk, sv in set_ops.items():
                parts = sk.split(".")
                d = new_doc
                for p in parts[:-1]:
                    if p not in d:
                        d[p] = {}
                    d = d[p]
                d[parts[-1]] = copy.deepcopy(sv)
            self.insert_one(new_doc)
            res = UpdateResult()
            res.modified_count = 1
            return res

        return UpdateResult()

    def delete_many(self, query: Optional[Dict[str, Any]] = None) -> Any:
        query = query or {}
        deleted_count = 0
        to_delete = []
        for doc_id, doc in self.data.items():
            if self._match(doc, query):
                to_delete.append(doc_id)
        for doc_id in to_delete:
            del self.data[doc_id]
            deleted_count += 1
        if deleted_count > 0:
            self._save_data()
        
        class DeleteResult:
            deleted_count = 0
        res = DeleteResult()
        res.deleted_count = deleted_count
        return res

    def count_documents(self, query: Optional[Dict[str, Any]] = None) -> int:
        return len(self.find(query))

    def create_index(self, keys: Any, unique: bool = False) -> None:
        pass

class MockDatabase:
    """Mock PyMongo Database holding collections synced to disk."""
    def __init__(self, db_file: str) -> None:
        self.db_file = db_file
        self.collections: Dict[str, MockCollection] = {}

    def __getitem__(self, name: str) -> MockCollection:
        if name not in self.collections:
            self.collections[name] = MockCollection(name, self.db_file)
        return self.collections[name]

class MockMongoClient:
    """Mock PyMongo MongoClient providing database access and ping."""
    def __init__(self, db_file: str) -> None:
        self.db = MockDatabase(db_file)

    def __getitem__(self, name: str) -> MockDatabase:
        return self.db

    @property
    def admin(self) -> Any:
        class Admin:
            def command(self, cmd: str) -> Dict[str, int]:
                return {"ok": 1}
        return Admin()

# =========================================================================
# Connection Manager
# =========================================================================

class MongoDBManager:
    """Manages connection and checks for MongoDB, falling back to persistent mock if needed."""

    def __init__(self) -> None:
        self.client: Any = None
        self.db: Any = None
        self.is_mock: bool = False

    def connect(self) -> None:
        """
        Connects to MongoDB and verifies the connection.
        Falls back to persistent file-backed MockMongoClient if MongoDB is offline.
        """
        try:
            self.client = MongoClient(
                settings.MONGODB_URI,
                serverSelectionTimeoutMS=3000
            )
            self.client.admin.command("ping")
            self.db = self.client[settings.MONGODB_DATABASE]
            self.is_mock = False
            
            from src.database.models import init_indexes
            init_indexes(self.db)
            logger.info("Successfully connected to MongoDB.")
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.warning(
                f"Failed to connect to MongoDB ({e}). "
                f"Falling back to persistent mock DB at: {MOCK_DB_FILE}"
            )
            self.client = MockMongoClient(MOCK_DB_FILE)
            self.db = self.client[settings.MONGODB_DATABASE]
            self.is_mock = True

    def get_db(self) -> Any:
        """Returns the database instance. Connects if not already connected."""
        if self.db is None:
            self.connect()
        return self.db

# Global manager instance
db_manager = MongoDBManager()
