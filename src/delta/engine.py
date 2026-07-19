"""
Knowledge Delta Engine.

Compares incoming parsed and validated entities against existing MongoDB records.
Applies confidence thresholds to filter out noisy updates, commits valid updates,
and registers logs in the ChangeHistory collection.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from loguru import logger

from src.config.config import settings
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

class KnowledgeDeltaEngine:
    """Calculates updates confidence, resolves diffs, and writes change logs."""

    def __init__(self):
        self.startup_repo = StartupRepository()
        self.product_repo = ProductRepository()
        self.paper_repo = ResearchPaperRepository()
        self.job_repo = JobRepository()
        self.news_repo = NewsRepository()
        self.change_repo = ChangeHistoryRepository()

    def get_source_confidence(self, priority: str) -> float:
        """Maps source priority to a confidence score."""
        priority_upper = priority.upper()
        if priority_upper == "HIGH":
            return 0.95
        elif priority_upper == "MEDIUM":
            return 0.80
        elif priority_upper == "LOW":
            return 0.60
        return 0.50

    async def process_entity_update(self, new_entity: BaseEntity, source_priority: str) -> Tuple[str, bool]:
        """
        Compares new_entity with existing db record.
        Decides if an update is warranted based on confidence thresholds.
        Returns a tuple: (status_message, was_updated).
        """
        record_type = new_entity.recordType
        confidence = self.get_source_confidence(source_priority)
        threshold = settings.DELTA_CONFIDENCE_THRESHOLD

        if record_type == EntityRecordType.STARTUP:
            return await self._process_startup(new_entity, confidence, threshold)
        elif record_type == EntityRecordType.PRODUCT:
            return await self._process_product(new_entity, confidence, threshold)
        elif record_type == EntityRecordType.RESEARCH_PAPER:
            return await self._process_paper(new_entity, confidence, threshold)
        elif record_type == EntityRecordType.JOB:
            return await self._process_job(new_entity)
        elif record_type == EntityRecordType.NEWS:
            return await self._process_news(new_entity)
            
        return "Unknown record type", False

    async def _process_startup(self, entity: Any, confidence: float, threshold: float) -> Tuple[str, bool]:
        name = entity.content.entityName
        existing = self.startup_repo.find_one({"content.entityName": name})
        
        if not existing:
            self.startup_repo.insert(entity.model_dump())
            logger.info(f"Inserted new startup record: '{name}'")
            return "Inserted new record", True

        old_count = existing["content"]["data"].get("employeeCount")
        new_count = entity.content.data.employeeCount

        if old_count != new_count:
            if confidence < threshold:
                logger.warning(
                    f"Startup update rejected for '{name}' | "
                    f"Confidence {confidence:.2f} is below threshold {threshold:.2f}"
                )
                return "Confidence below threshold", False
                
            history_record = ChangeHistory(
                entityName=name,
                recordType=EntityRecordType.STARTUP,
                field="employeeCount",
                oldValue=old_count,
                newValue=new_count,
                confidence=confidence
            )
            self.change_repo.insert(history_record.model_dump())
            
            # Update specific fields in database
            self.startup_repo.update_one(
                {"content.entityName": name},
                {"$set": {
                    "content.data.employeeCount": new_count,
                    "updatedAt": datetime.now(timezone.utc)
                }}
            )
            
            logger.info(f"Updated startup '{name}' employeeCount: {old_count} -> {new_count}")
            return "Updated record fields", True

        return "No fields changed", False

    async def _process_product(self, entity: Any, confidence: float, threshold: float) -> Tuple[str, bool]:
        startup_name = entity.content.startupName
        existing = self.product_repo.find_one({"content.startupName": startup_name})

        if not existing:
            self.product_repo.insert(entity.model_dump())
            logger.info(f"Inserted new product record: '{startup_name}'")
            return "Inserted new record", True

        old_pricing = existing["content"].get("pricingModel")
        new_pricing = entity.content.pricingModel.value

        if old_pricing != new_pricing:
            if confidence < threshold:
                logger.warning(
                    f"Product update rejected for '{startup_name}' | "
                    f"Confidence {confidence:.2f} is below threshold {threshold:.2f}"
                )
                return "Confidence below threshold", False

            history_record = ChangeHistory(
                entityName=startup_name,
                recordType=EntityRecordType.PRODUCT,
                field="pricingModel",
                oldValue=old_pricing,
                newValue=new_pricing,
                confidence=confidence
            )
            self.change_repo.insert(history_record.model_dump())

            self.product_repo.update_one(
                {"content.startupName": startup_name},
                {"$set": {
                    "content.pricingModel": new_pricing,
                    "updatedAt": datetime.now(timezone.utc)
                }}
            )

            logger.info(f"Updated product '{startup_name}' pricingModel: {old_pricing} -> {new_pricing}")
            return "Updated record fields", True

        return "No fields changed", False

    async def _process_paper(self, entity: Any, confidence: float, threshold: float) -> Tuple[str, bool]:
        title = entity.content.title
        existing = self.paper_repo.find_one({"content.title": title})

        if not existing:
            self.paper_repo.insert(entity.model_dump())
            logger.info(f"Inserted new research paper record: '{title}'")
            return "Inserted new record", True

        old_git = existing["content"].get("github_url")
        new_git = entity.content.github_url

        if old_git != new_git:
            if confidence < threshold:
                return "Confidence below threshold", False

            history_record = ChangeHistory(
                entityName=title,
                recordType=EntityRecordType.RESEARCH_PAPER,
                field="github_url",
                oldValue=old_git,
                newValue=new_git,
                confidence=confidence
            )
            self.change_repo.insert(history_record.model_dump())

            self.paper_repo.update_one(
                {"content.title": title},
                {"$set": {
                    "content.github_url": new_git,
                    "updatedAt": datetime.now(timezone.utc)
                }}
            )

            logger.info(f"Updated research paper '{title}' github_url: {old_git} -> {new_git}")
            return "Updated record fields", True

        return "No fields changed", False

    async def _process_job(self, entity: Any) -> Tuple[str, bool]:
        company = entity.content.company
        role = entity.content.role_family
        existing = self.job_repo.find_one({"content.company": company, "content.role_family": role})
        
        if not existing:
            self.job_repo.insert(entity.model_dump())
            logger.info(f"Inserted new job listing: '{company}' - '{role}'")
            return "Inserted new record", True
            
        return "Job listing already exists", False

    async def _process_news(self, entity: Any) -> Tuple[str, bool]:
        title = entity.content.title
        existing = self.news_repo.find_one({"content.title": title})
        
        if not existing:
            self.news_repo.insert(entity.model_dump())
            logger.info(f"Inserted new news article: '{title}'")
            return "Inserted new record", True
            
        return "News article already exists", False
