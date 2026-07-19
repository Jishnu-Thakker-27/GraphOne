"""
Entity Validator.

Validates raw extracted entity structures against Pydantic definitions,
injecting source registry details during verification.
"""

from typing import Any, Dict, Optional, Union
from loguru import logger
from pydantic import ValidationError
from src.pipeline.schemas import (
    StartupEntity,
    ProductEntity,
    ResearchPaperEntity,
    JobEntity,
    NewsEntity,
    SourceInfo,
    EntityRecordType,
)

class EntityValidator:
    """Validates extracted entity payloads against canonical Pydantic schemas."""

    @staticmethod
    def validate(
        raw_data: Dict[str, Any], 
        source_info: SourceInfo
    ) -> Optional[Union[StartupEntity, ProductEntity, ResearchPaperEntity, JobEntity, NewsEntity]]:
        """
        Validates a raw dictionary representing an extracted entity.
        Injects source metadata and returns the parsed Pydantic entity model,
        or None if validation fails.
        """
        record_type_str = raw_data.get("recordType")
        if not record_type_str:
            logger.warning("Validation failed: Missing recordType in raw data")
            return None

        # Build standard payload incorporating source parameters
        payload = {
            "schemaVersion": raw_data.get("schemaVersion", "1.0"),
            "recordType": record_type_str,
            "source": {
                "name": source_info.name,
                "url": source_info.url
            },
            "content": raw_data.get("content")
        }

        try:
            if record_type_str == EntityRecordType.STARTUP.value:
                return StartupEntity(**payload)
            elif record_type_str == EntityRecordType.PRODUCT.value:
                return ProductEntity(**payload)
            elif record_type_str == EntityRecordType.RESEARCH_PAPER.value:
                return ResearchPaperEntity(**payload)
            elif record_type_str == EntityRecordType.JOB.value:
                return JobEntity(**payload)
            elif record_type_str == EntityRecordType.NEWS.value:
                return NewsEntity(**payload)
            else:
                logger.warning(f"Validation failed: Unknown record type '{record_type_str}'")
                return None
        except ValidationError as e:
            logger.error(f"Pydantic Validation Error for type '{record_type_str}': {e}")
            return None
