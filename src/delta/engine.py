"""
Deterministic Knowledge Delta Engine.

Compares incoming parsed and validated entities against existing MongoDB records
using a deterministic field-level merge algorithm and source precedence logic.
Tracks changes in the ChangeHistory collection and calculates stable entity fingerprints.
"""

import hashlib
import json
import copy
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple
from loguru import logger
from pydantic import BaseModel

from src.config.registry import SourceRegistry
from src.pipeline.schemas import (
    BaseEntity,
    ChangeHistory,
    EntityRecordType,
)
from src.database.repositories import (
    StartupRepository,
    ProductRepository,
    ResearchPaperRepository,
    JobRepository,
    NewsRepository,
    ChangeHistoryRepository,
)
from src.utils.date_normalizer import DateNormalizer

# =========================================================================
# Result Schema
# =========================================================================

class DeltaResult(BaseModel):
    """Structured result representing the outcome of a knowledge delta run."""
    action: Literal["INSERT", "UPDATE", "MERGE", "SKIP"]
    changed_fields: List[str]
    reason: str
    existing_priority: int
    incoming_priority: int
    fingerprint_changed: bool

# =========================================================================
# Helper Functions
# =========================================================================

def normalize_url(url: Any) -> str:
    """Normalizes a URL to ensure clean, deterministic comparisons."""
    if not isinstance(url, str) or not url:
        return ""
    url = url.lower().strip()
    url = url.replace("http://", "").replace("https://", "")
    url = url.replace("www.", "")
    if url.endswith("/"):
        url = url[:-1]
    return url

def get_flat_fields(d: Any, prefix: str = "") -> Dict[str, Any]:
    """Flattens nested dictionaries into a single dot-notated dictionary."""
    flat = {}
    if isinstance(d, dict):
        for k, v in d.items():
            key = f"{prefix}.{k}" if prefix else k
            flat.update(get_flat_fields(v, key))
    else:
        flat[prefix] = d
    return flat

def set_nested_value(d: dict, path: str, value: Any) -> None:
    """Sets a nested value inside a dictionary using a dot-notated key path."""
    parts = path.split(".")
    curr = d
    for p in parts[:-1]:
        if p not in curr or not isinstance(curr[p], dict):
            curr[p] = {}
        curr = curr[p]
    curr[parts[-1]] = value

# =========================================================================
# Engine Definition
# =========================================================================

class KnowledgeDeltaEngine:
    """Deterministic merge engine that compares, updates, and logs entity updates."""

    def __init__(self):
        self.startup_repo = StartupRepository()
        self.product_repo = ProductRepository()
        self.paper_repo = ResearchPaperRepository()
        self.job_repo = JobRepository()
        self.news_repo = NewsRepository()
        self.change_repo = ChangeHistoryRepository()
        
        # Load registry to retrieve priority precedence levels
        self.registry = SourceRegistry()
        self.precedence_map = {}
        try:
            for s in self.registry.load():
                self.precedence_map[s.name] = s.precedence
        except Exception as e:
            logger.warning(f"Failed to load source registry for precedence levels: {e}")

    def get_source_precedence(self, source_name: str) -> int:
        """Retrieves precedence value for a source from registry. Defaults to 50."""
        return self.precedence_map.get(source_name, 50)

    def calculate_fingerprint(self, entity: BaseEntity) -> str:
        """
        Calculates a deterministic SHA-256 fingerprint hash of stable entity fields:
        Canonical Name, Entity Type, Normalized Content fields, and Content Hash.
        Excludes dynamic attributes like timestamps, source URLs, and database IDs.
        """
        content_dict = entity.content.model_dump()
        
        # Normalize URLs in content_dict to stabilize fingerprint under URL formatting variations
        for k, v in list(content_dict.items()):
            if isinstance(v, str) and ("url" in k.lower() or v.startswith("http")):
                content_dict[k] = normalize_url(v)
                
        # Identify canonical name
        name = ""
        if hasattr(entity.content, "entityName"):
            name = entity.content.entityName
        elif hasattr(entity.content, "startupName"):
            name = entity.content.startupName
        elif hasattr(entity.content, "title"):
            name = entity.content.title
        elif hasattr(entity.content, "company"):
            name = entity.content.company
            
        stable_metadata = {
            "source_name": entity.source.name
        }
        
        # Extract GitHub metadata if available
        github_metadata = {}
        for k in ["github_url", "github_stars", "github_forks", "github_language", "github_description", "github_updated_at"]:
            if k in content_dict:
                github_metadata[k] = content_dict[k]
                
        fingerprint_dict = {
            "canonical_name": name,
            "entity_type": entity.recordType.value,
            "content": content_dict,
            "github_metadata": github_metadata,
            "stable_metadata": stable_metadata,
            "content_hash": entity.content_hash or ""
        }
        
        data_str = json.dumps(fingerprint_dict, sort_keys=True, default=str)
        return hashlib.sha256(data_str.encode("utf-8")).hexdigest()

    async def process_entity_update(self, new_entity: BaseEntity) -> DeltaResult:
        """
        Compares new_entity with existing record.
        Performs field-level merges and logs actions to ChangeHistory.
        Returns a structured DeltaResult.
        """
        # Calculate fingerprint for incoming entity
        incoming_fingerprint = self.calculate_fingerprint(new_entity)
        new_entity.entity_fingerprint = incoming_fingerprint

        record_type = new_entity.recordType
        incoming_precedence = self.get_source_precedence(new_entity.source.name)

        if record_type == EntityRecordType.STARTUP:
            return await self._process_startup(new_entity, incoming_precedence, incoming_fingerprint)
        elif record_type == EntityRecordType.PRODUCT:
            return await self._process_product(new_entity, incoming_precedence, incoming_fingerprint)
        elif record_type == EntityRecordType.RESEARCH_PAPER:
            return await self._process_paper(new_entity, incoming_precedence, incoming_fingerprint)
        elif record_type == EntityRecordType.JOB:
            return await self._process_job(new_entity, incoming_precedence, incoming_fingerprint)
        elif record_type == EntityRecordType.NEWS:
            return await self._process_news(new_entity, incoming_precedence, incoming_fingerprint)
            
        return DeltaResult(
            action="SKIP",
            changed_fields=[],
            reason=f"Unsupported record type: {record_type}",
            existing_priority=0,
            incoming_priority=incoming_precedence,
            fingerprint_changed=True
        )

    async def _process_startup(self, entity: Any, incoming_prec: int, incoming_fingerprint: str) -> DeltaResult:
        name = entity.content.entityName
        existing = self.startup_repo.find_one({"content.entityName": name})
        
        if not existing:
            # Document does not exist: INSERT
            entity_dump = entity.model_dump()
            self.startup_repo.insert(entity_dump)
            
            # Log insertion in history
            history = ChangeHistory(
                entity_id=name,
                entity_type="STARTUP",
                operation="INSERT",
                changed_fields=["all"],
                old_values={},
                new_values=entity.content.model_dump(),
                source=entity.source.name,
                source_priority=incoming_prec,
                observed_at=entity.collectedAt,
                updated_at=entity.collectedAt,
                change_reason="Initial record ingestion"
            )
            self.change_repo.insert(history.model_dump())
            
            logger.info(f"Inserted new startup record: '{name}'")
            return DeltaResult(
                action="INSERT",
                changed_fields=[],
                reason="Initial record ingestion completed",
                existing_priority=0,
                incoming_priority=incoming_prec,
                fingerprint_changed=True
            )

        # Document exists: check fingerprint
        existing_fingerprint = existing.get("entity_fingerprint")
        if existing_fingerprint == incoming_fingerprint:
            # Fingerprints match: SKIP
            # Update observedAt time to the newest observation
            self.startup_repo.update_one(
                {"content.entityName": name},
                {"$set": {"observedAt": entity.collectedAt}}
            )
            return DeltaResult(
                action="SKIP",
                changed_fields=[],
                reason="Fingerprint matches, no changes detected.",
                existing_priority=self.get_source_precedence(existing["source"]["name"]),
                incoming_priority=incoming_prec,
                fingerprint_changed=False
            )

        # Merge fields
        existing_priority = self.get_source_precedence(existing["source"]["name"])
        result = self._merge_content_fields(existing["content"], entity.content.model_dump(), existing_priority, incoming_prec)
        
        if not result.changed_fields:
            # Update observed time anyway
            self.startup_repo.update_one(
                {"content.entityName": name},
                {"$set": {"observedAt": entity.collectedAt}}
            )
            return DeltaResult(
                action="SKIP",
                changed_fields=[],
                reason="Conflicting fields rejected due to lower priority precedence",
                existing_priority=existing_priority,
                incoming_priority=incoming_prec,
                fingerprint_changed=True
            )

        # Perform updates
        update_set = {
            "content": result.merged_content,
            "entity_fingerprint": incoming_fingerprint,
            "observedAt": entity.collectedAt,
            "updatedAt": datetime.now(timezone.utc)
        }
        self.startup_repo.update_one({"content.entityName": name}, {"$set": update_set})
        
        # Log merge history
        history = ChangeHistory(
            entity_id=name,
            entity_type="STARTUP",
            operation="MERGE",
            changed_fields=result.changed_fields,
            old_values=result.old_values,
            new_values=result.new_values,
            source=entity.source.name,
            source_priority=incoming_prec,
            observed_at=entity.collectedAt,
            updated_at=update_set["updatedAt"],
            change_reason="Deterministic field-level merge"
        )
        self.change_repo.insert(history.model_dump())
        
        logger.info(f"Merged startup '{name}' fields: {result.changed_fields}")
        return DeltaResult(
            action="MERGE",
            changed_fields=result.changed_fields,
            reason="Field-level merge completed",
            existing_priority=existing_priority,
            incoming_priority=incoming_prec,
            fingerprint_changed=True
        )

    async def _process_product(self, entity: Any, incoming_prec: int, incoming_fingerprint: str) -> DeltaResult:
        startup_name = entity.content.startupName
        existing = self.product_repo.find_one({"content.startupName": startup_name})

        if not existing:
            entity_dump = entity.model_dump()
            self.product_repo.insert(entity_dump)
            
            history = ChangeHistory(
                entity_id=startup_name,
                entity_type="PRODUCT",
                operation="INSERT",
                changed_fields=["all"],
                old_values={},
                new_values=entity.content.model_dump(),
                source=entity.source.name,
                source_priority=incoming_prec,
                observed_at=entity.collectedAt,
                updated_at=entity.collectedAt,
                change_reason="Initial record ingestion"
            )
            self.change_repo.insert(history.model_dump())
            
            logger.info(f"Inserted new product record: '{startup_name}'")
            return DeltaResult(
                action="INSERT",
                changed_fields=[],
                reason="Initial record ingestion completed",
                existing_priority=0,
                incoming_priority=incoming_prec,
                fingerprint_changed=True
            )

        existing_fingerprint = existing.get("entity_fingerprint")
        if existing_fingerprint == incoming_fingerprint:
            self.product_repo.update_one(
                {"content.startupName": startup_name},
                {"$set": {"observedAt": entity.collectedAt}}
            )
            return DeltaResult(
                action="SKIP",
                changed_fields=[],
                reason="Fingerprint matches, no changes detected.",
                existing_priority=self.get_source_precedence(existing["source"]["name"]),
                incoming_priority=incoming_prec,
                fingerprint_changed=False
            )

        existing_priority = self.get_source_precedence(existing["source"]["name"])
        result = self._merge_content_fields(existing["content"], entity.content.model_dump(), existing_priority, incoming_prec)

        if not result.changed_fields:
            self.product_repo.update_one(
                {"content.startupName": startup_name},
                {"$set": {"observedAt": entity.collectedAt}}
            )
            return DeltaResult(
                action="SKIP",
                changed_fields=[],
                reason="Conflicting fields rejected due to lower priority precedence",
                existing_priority=existing_priority,
                incoming_priority=incoming_prec,
                fingerprint_changed=True
            )

        update_set = {
            "content": result.merged_content,
            "entity_fingerprint": incoming_fingerprint,
            "observedAt": entity.collectedAt,
            "updatedAt": datetime.now(timezone.utc)
        }
        self.product_repo.update_one({"content.startupName": startup_name}, {"$set": update_set})

        history = ChangeHistory(
            entity_id=startup_name,
            entity_type="PRODUCT",
            operation="MERGE",
            changed_fields=result.changed_fields,
            old_values=result.old_values,
            new_values=result.new_values,
            source=entity.source.name,
            source_priority=incoming_prec,
            observed_at=entity.collectedAt,
            updated_at=update_set["updatedAt"],
            change_reason="Deterministic field-level merge"
        )
        self.change_repo.insert(history.model_dump())

        logger.info(f"Merged product '{startup_name}' fields: {result.changed_fields}")
        return DeltaResult(
            action="MERGE",
            changed_fields=result.changed_fields,
            reason="Field-level merge completed",
            existing_priority=existing_priority,
            incoming_priority=incoming_prec,
            fingerprint_changed=True
        )

    async def _process_paper(self, entity: Any, incoming_prec: int, incoming_fingerprint: str) -> DeltaResult:
        title = entity.content.title
        existing = self.paper_repo.find_one({"content.title": title})

        if not existing:
            entity_dump = entity.model_dump()
            self.paper_repo.insert(entity_dump)

            history = ChangeHistory(
                entity_id=title,
                entity_type="RESEARCH_PAPER",
                operation="INSERT",
                changed_fields=["all"],
                old_values={},
                new_values=entity.content.model_dump(),
                source=entity.source.name,
                source_priority=incoming_prec,
                observed_at=entity.collectedAt,
                updated_at=entity.collectedAt,
                change_reason="Initial record ingestion"
            )
            self.change_repo.insert(history.model_dump())

            logger.info(f"Inserted new research paper record: '{title}'")
            return DeltaResult(
                action="INSERT",
                changed_fields=[],
                reason="Initial record ingestion completed",
                existing_priority=0,
                incoming_priority=incoming_prec,
                fingerprint_changed=True
            )

        existing_fingerprint = existing.get("entity_fingerprint")
        if existing_fingerprint == incoming_fingerprint:
            self.paper_repo.update_one(
                {"content.title": title},
                {"$set": {"observedAt": entity.collectedAt}}
            )
            return DeltaResult(
                action="SKIP",
                changed_fields=[],
                reason="Fingerprint matches, no changes detected.",
                existing_priority=self.get_source_precedence(existing["source"]["name"]),
                incoming_priority=incoming_prec,
                fingerprint_changed=False
            )

        existing_priority = self.get_source_precedence(existing["source"]["name"])
        result = self._merge_content_fields(existing["content"], entity.content.model_dump(), existing_priority, incoming_prec)

        if not result.changed_fields:
            self.paper_repo.update_one(
                {"content.title": title},
                {"$set": {"observedAt": entity.collectedAt}}
            )
            return DeltaResult(
                action="SKIP",
                changed_fields=[],
                reason="Conflicting fields rejected due to lower priority precedence",
                existing_priority=existing_priority,
                incoming_priority=incoming_prec,
                fingerprint_changed=True
            )

        update_set = {
            "content": result.merged_content,
            "entity_fingerprint": incoming_fingerprint,
            "observedAt": entity.collectedAt,
            "updatedAt": datetime.now(timezone.utc)
        }
        self.paper_repo.update_one({"content.title": title}, {"$set": update_set})

        history = ChangeHistory(
            entity_id=title,
            entity_type="RESEARCH_PAPER",
            operation="MERGE",
            changed_fields=result.changed_fields,
            old_values=result.old_values,
            new_values=result.new_values,
            source=entity.source.name,
            source_priority=incoming_prec,
            observed_at=entity.collectedAt,
            updated_at=update_set["updatedAt"],
            change_reason="Deterministic field-level merge"
        )
        self.change_repo.insert(history.model_dump())

        logger.info(f"Merged research paper '{title}' fields: {result.changed_fields}")
        return DeltaResult(
            action="MERGE",
            changed_fields=result.changed_fields,
            reason="Field-level merge completed",
            existing_priority=existing_priority,
            incoming_priority=incoming_prec,
            fingerprint_changed=True
        )

    async def _process_job(self, entity: Any, incoming_prec: int, incoming_fingerprint: str) -> DeltaResult:
        company = entity.content.company
        role = entity.content.role_family
        existing = self.job_repo.find_one({"content.company": company, "content.role_family": role})
        
        if not existing:
            entity_dump = entity.model_dump()
            self.job_repo.insert(entity_dump)
            
            history = ChangeHistory(
                entity_id=f"{company} - {role}",
                entity_type="JOB",
                operation="INSERT",
                changed_fields=["all"],
                old_values={},
                new_values=entity.content.model_dump(),
                source=entity.source.name,
                source_priority=incoming_prec,
                observed_at=entity.collectedAt,
                updated_at=entity.collectedAt,
                change_reason="Initial job listing ingestion"
            )
            self.change_repo.insert(history.model_dump())
            
            logger.info(f"Inserted new job listing: '{company}' - '{role}'")
            return DeltaResult(
                action="INSERT",
                changed_fields=[],
                reason="Initial record ingestion completed",
                existing_priority=0,
                incoming_priority=incoming_prec,
                fingerprint_changed=True
            )
            
        # Jobs are append-only. Skip updating if it already exists.
        return DeltaResult(
            action="SKIP",
            changed_fields=[],
            reason="Job listing already exists",
            existing_priority=self.get_source_precedence(existing["source"]["name"]),
            incoming_priority=incoming_prec,
            fingerprint_changed=False
        )

    async def _process_news(self, entity: Any, incoming_prec: int, incoming_fingerprint: str) -> DeltaResult:
        title = entity.content.title
        existing = self.news_repo.find_one({"content.title": title})
        
        if not existing:
            entity_dump = entity.model_dump()
            self.news_repo.insert(entity_dump)
            
            history = ChangeHistory(
                entity_id=title,
                entity_type="NEWS",
                operation="INSERT",
                changed_fields=["all"],
                old_values={},
                new_values=entity.content.model_dump(),
                source=entity.source.name,
                source_priority=incoming_prec,
                observed_at=entity.collectedAt,
                updated_at=entity.collectedAt,
                change_reason="Initial news ingestion"
            )
            self.change_repo.insert(history.model_dump())
            
            logger.info(f"Inserted new news article: '{title}'")
            return DeltaResult(
                action="INSERT",
                changed_fields=[],
                reason="Initial record ingestion completed",
                existing_priority=0,
                incoming_priority=incoming_prec,
                fingerprint_changed=True
            )
            
        # News is append-only. Skip updating if it already exists.
        return DeltaResult(
            action="SKIP",
            changed_fields=[],
            reason="News article already exists",
            existing_priority=self.get_source_precedence(existing["source"]["name"]),
            incoming_priority=incoming_prec,
            fingerprint_changed=False
        )

    # =========================================================================
    # Merge Logic Execution
    # =========================================================================

    class MergeResult:
        def __init__(self, merged_content: dict, changed_fields: List[str], old_values: dict, new_values: dict):
            self.merged_content = merged_content
            self.changed_fields = changed_fields
            self.old_values = old_values
            self.new_values = new_values

    def _merge_content_fields(self, existing: dict, incoming: dict, existing_priority: int, incoming_priority: int) -> MergeResult:
        """Compares flat fields and applies deterministic merge rules."""
        existing_flat = get_flat_fields(existing)
        incoming_flat = get_flat_fields(incoming)
        
        changed_fields = []
        old_values = {}
        new_values = {}
        
        merged_content = copy.deepcopy(existing)
        
        for path, incoming_val in incoming_flat.items():
            # Check if database value is missing
            is_missing = (path not in existing_flat) or (existing_flat[path] is None) or (existing_flat[path] == "")
            
            if is_missing:
                # Rule 1: Always accept incoming value for missing database fields
                if incoming_val is not None and incoming_val != "":
                    changed_fields.append(path)
                    old_values[path] = None
                    new_values[path] = incoming_val
                    set_nested_value(merged_content, path, incoming_val)
                continue
                
            existing_val = existing_flat[path]
            
            # Rule 2: Lists -> Merge using order-preserving union
            if isinstance(incoming_val, list) and isinstance(existing_val, list):
                merged_list = list(dict.fromkeys(existing_val + incoming_val))
                if merged_list != existing_val:
                    changed_fields.append(path)
                    old_values[path] = existing_val
                    new_values[path] = merged_list
                    set_nested_value(merged_content, path, merged_list)
                continue
                
            # Rule 3: URLs -> Normalize before comparison
            is_url_field = "url" in path.lower() or (isinstance(incoming_val, str) and incoming_val.startswith("http"))
            if is_url_field:
                if normalize_url(existing_val) == normalize_url(incoming_val):
                    # Identical when normalized: skip
                    continue
                    
            # Rule 4: Publication Date -> Keep earliest date
            if path == "published_date":
                dt_existing = existing_val if isinstance(existing_val, datetime) else DateNormalizer.normalize(existing_val)
                dt_incoming = incoming_val if isinstance(incoming_val, datetime) else DateNormalizer.normalize(incoming_val)
                if dt_existing and dt_incoming:
                    earliest = min(dt_existing, dt_incoming)
                    # Keep the string format of whichever is earlier
                    target_val = existing_val if earliest == dt_existing else incoming_val
                    if existing_val != target_val:
                        changed_fields.append(path)
                        old_values[path] = existing_val
                        new_values[path] = target_val
                        set_nested_value(merged_content, path, target_val)
                continue

            # Check if values are identical
            if existing_val == incoming_val:
                continue
                
            # Rule 5: Conflict resolution based on priority precedence
            if incoming_priority > existing_priority:
                # Incoming precedence is higher: accept update
                changed_fields.append(path)
                old_values[path] = existing_val
                new_values[path] = incoming_val
                set_nested_value(merged_content, path, incoming_val)
            elif incoming_priority == existing_priority:
                # Equal precedence
                # Numeric fields: Replace only if incoming has strictly HIGHER precedence
                is_numeric = isinstance(incoming_val, (int, float)) and not isinstance(incoming_val, bool)
                if is_numeric:
                    continue
                else:
                    # Non-numeric fields: Overwrite on equal priority (temporal overwrite)
                    changed_fields.append(path)
                    old_values[path] = existing_val
                    new_values[path] = incoming_val
                    set_nested_value(merged_content, path, incoming_val)
            else:
                # Incoming precedence is lower: reject update
                continue
                
        return self.MergeResult(merged_content, changed_fields, old_values, new_values)
