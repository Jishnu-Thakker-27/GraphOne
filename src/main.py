import sys
from src.config.config import settings
from src.config.registry import SourceRegistry
from src.database.mongodb import db_manager
from src.database.models import init_indexes

def main() -> None:
    print("Adaptive Intelligence Ingestion Pipeline (AIIP) Initialized.\n")
    
    # 1. Validate Environment configuration
    try:
        warnings = settings.validate()
        for warning in warnings:
            print(f"WARNING: {warning}")
    except ValueError as e:
        print(f"CRITICAL CONFIG ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. Check Database Connection & Initialize Indexes
    try:
        print("Checking database connection...")
        db = db_manager.get_db()
        init_indexes(db)
        print("Database connection verified and indexes initialized.\n")
    except Exception as e:
        print(f"CRITICAL DATABASE ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # 3. Load and Validate Source configuration
    try:
        registry = SourceRegistry()
        enabled_sources = registry.load()
        print(f"Loaded {len(enabled_sources)} sources.\n")
        for source in enabled_sources:
            status = "[ENABLED]" if source.enabled else "[DISABLED]"
            print(f"{status} {source.name} ({source.category.value}) - Method: {source.extraction_method.value}")
    except Exception as e:
        print(f"CRITICAL SOURCE REGISTRY ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
