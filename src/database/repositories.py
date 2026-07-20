"""
Repository Layer.

Encapsulates data access and storage logic for MongoDB collections.
"""

from typing import Any, Dict, List, Optional
from pymongo.database import Database
from src.database.mongodb import db_manager
from src.database.models import (
    COLL_STARTUPS,
    COLL_PRODUCTS,
    COLL_PAPERS,
    COLL_JOBS,
    COLL_NEWS,
    COLL_CHANGE_HISTORY,
    COLL_ENTITY_MAPPINGS,
    COLL_CONTENT_CACHE,
)

class BaseRepository:
    """Base repository providing common MongoDB client operations."""

    def __init__(self, collection_name: str) -> None:
        self.collection_name = collection_name
        self._db: Optional[Database] = None

    @property
    def db(self) -> Database:
        """Lazily connects to the database and returns the Database object."""
        if self._db is None:
            self._db = db_manager.get_db()
        return self._db

    @property
    def collection(self):
        """Returns the collection object."""
        return self.db[self.collection_name]

    def insert(self, document: Dict[str, Any]) -> str:
        """Inserts a single document and returns its ID."""
        result = self.collection.insert_one(document)
        return str(result.inserted_id)

    def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Finds a single document matching the query."""
        return self.collection.find_one(query)

    def update_one(self, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = False) -> int:
        """Updates a single document and returns the matched count."""
        result = self.collection.update_one(query, update, upsert=upsert)
        return result.modified_count

    def find(self, query: Dict[str, Any] = None, sort_by: List[tuple] = None, limit: int = 0, skip: int = 0) -> List[Dict[str, Any]]:
        """Finds list of documents matching the query."""
        query = query or {}
        cursor = self.collection.find(query)
        if sort_by:
            cursor = cursor.sort(sort_by)
        if skip > 0:
            cursor = cursor.skip(skip)
        if limit > 0:
            cursor = cursor.limit(limit)
        return list(cursor)

    def count(self, query: Dict[str, Any] = None) -> int:
        """Counts documents matching the query."""
        query = query or {}
        return self.collection.count_documents(query)

    def delete_many(self, query: Dict[str, Any] = None) -> int:
        """Deletes multiple documents matching the query and returns the deleted count."""
        query = query or {}
        result = self.collection.delete_many(query)
        return result.deleted_count


class StartupRepository(BaseRepository):
    """Repository for Startup entities."""
    def __init__(self) -> None:
        super().__init__(COLL_STARTUPS)

    def find_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        return self.find_one({"content.entityName": name})


class ProductRepository(BaseRepository):
    """Repository for Product entities."""
    def __init__(self) -> None:
        super().__init__(COLL_PRODUCTS)

    def find_by_name_and_url(self, startup_name: str, url: str) -> Optional[Dict[str, Any]]:
        return self.find_one({"content.startupName": startup_name, "source.url": url})


class ResearchPaperRepository(BaseRepository):
    """Repository for Research Paper entities."""
    def __init__(self) -> None:
        super().__init__(COLL_PAPERS)

    def find_by_url(self, paper_url: str) -> Optional[Dict[str, Any]]:
        return self.find_one({"content.paper_url": paper_url})


class JobRepository(BaseRepository):
    """Repository for Job postings."""
    def __init__(self) -> None:
        super().__init__(COLL_JOBS)


class NewsRepository(BaseRepository):
    """Repository for News signals."""
    def __init__(self) -> None:
        super().__init__(COLL_NEWS)

    def find_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        return self.find_one({"content.url": url})


class ChangeHistoryRepository(BaseRepository):
    """Repository for Change History Logs."""
    def __init__(self) -> None:
        super().__init__(COLL_CHANGE_HISTORY)


class EntityMappingRepository(BaseRepository):
    """Repository for Entity Name Mappings."""
    def __init__(self) -> None:
        super().__init__(COLL_ENTITY_MAPPINGS)

    def find_mapping(self, raw_name: str) -> Optional[Dict[str, Any]]:
        return self.find_one({"rawName": raw_name})

    def save_mapping(self, raw_name: str, canonical_name: str) -> None:
        self.update_one(
            {"rawName": raw_name},
            {"$set": {"rawName": raw_name, "canonicalName": canonical_name}},
            upsert=True
        )


class ContentCacheRepository(BaseRepository):
    """Repository for LLM extraction caching."""
    def __init__(self) -> None:
        super().__init__(COLL_CONTENT_CACHE)

    def get_cached(self, content_hash: str) -> Optional[Dict[str, Any]]:
        doc = self.find_one({"content_hash": content_hash})
        return doc.get("extraction") if doc else None

    def cache_extraction(self, content_hash: str, extraction: Dict[str, Any]) -> None:
        self.update_one(
            {"content_hash": content_hash},
            {"$set": {"content_hash": content_hash, "extraction": extraction}},
            upsert=True
        )
