"""
Strategy Selector.

Determines the optimal data extraction path (Rule-based/JSON-LD parsing vs. LLM extraction)
based on source configuration and content characteristics to minimize token usage.
"""

import re
from loguru import logger
from src.config.registry import SourceConfig, ExtractionMethod
from src.pipeline.schemas import ExtractionStrategy

class StrategySelector:
    """Selects the best extraction strategy (Rule-based, JSON-LD, or LLM) for crawled content."""

    @staticmethod
    def select_strategy(source: SourceConfig, content: str) -> ExtractionStrategy:
        """
        Determines the extraction strategy for a source and its retrieved content.
        Dynamically overrides configuration to use rule-based parsing if structured data (JSON-LD) is found.
        """
        # 1. If configured to use API, select JSON_API
        if source.extraction_method == ExtractionMethod.API:
            logger.info(f"Strategy selected: {ExtractionStrategy.JSON_API.value} (Configured for API) | Source: {source.name}")
            return ExtractionStrategy.JSON_API

        # 2. If configured to use Rule-based, select RULE_BASED
        if source.extraction_method == ExtractionMethod.RULE_BASED:
            logger.info(f"Strategy selected: {ExtractionStrategy.RULE_BASED.value} (Configured for Rule-based) | Source: {source.name}")
            return ExtractionStrategy.RULE_BASED

        # 3. Check for JSON-LD script block in content to dynamically bypass LLM and save tokens
        if "<script" in content and 'type="application/ld+json"' in content:
            logger.info(
                f"Strategy selected: {ExtractionStrategy.JSON_LD.value} (Dynamic Override: JSON-LD detected) | "
                f"Source: {source.name} | Bypassing LLM to save tokens"
            )
            return ExtractionStrategy.JSON_LD

        # 4. Default to LLM extraction if semantic reasoning on unstructured content is required
        logger.info(f"Strategy selected: {ExtractionStrategy.LLM.value} (Requires semantic extraction) | Source: {source.name}")
        return ExtractionStrategy.LLM
