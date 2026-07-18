"""
Database collection definitions and indexes.
"""

from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database

# Collection Name Constants
COLL_STARTUPS = "startups"
COLL_PRODUCTS = "products"
COLL_PAPERS = "research_papers"
COLL_JOBS = "jobs"
COLL_NEWS = "news"
COLL_CHANGE_HISTORY = "change_history"
COLL_ENTITY_MAPPINGS = "entity_mappings"
COLL_CONTENT_CACHE = "content_cache"

def init_indexes(db: Database) -> None:
    """
    Initializes indexes and unique constraints for collections.
    Prevents duplicate entries and ensures fast lookups.
    """
    # Startups: Unique index on canonical startup name
    db[COLL_STARTUPS].create_index([("content.entityName", ASCENDING)], unique=True)

    # Products: Unique index on startupName and source url combination
    db[COLL_PRODUCTS].create_index([("content.startupName", ASCENDING), ("source.url", ASCENDING)], unique=True)

    # Papers: Unique index on paper URL
    db[COLL_PAPERS].create_index([("content.paper_url", ASCENDING)], unique=True)

    # Jobs: Index company name and date for fast lookups
    db[COLL_JOBS].create_index([("content.company", ASCENDING), ("content.date", DESCENDING)])

    # News: Unique index on URL
    db[COLL_NEWS].create_index([("content.url", ASCENDING)], unique=True)

    # Change History: Index entityName and timestamp for audit trails
    db[COLL_CHANGE_HISTORY].create_index([("entityName", ASCENDING), ("timestamp", DESCENDING)])

    # Entity Mappings: Unique index on raw input name
    db[COLL_ENTITY_MAPPINGS].create_index([("rawName", ASCENDING)], unique=True)

    # Content Cache: Unique index on content hash (SHA-256) for LLM caching
    db[COLL_CONTENT_CACHE].create_index([("content_hash", ASCENDING)], unique=True)
