"""
Pipeline Processor.

Orchestrates semantic LLM extraction for unstructured normalized contents.
"""

import json
import hashlib
from typing import Any, Dict, List
from loguru import logger
from src.llm.client import MultiLLMClient
from src.pipeline.schemas import EntityRecordType
from src.database.repositories import ContentCacheRepository
from src.metrics.collector import metrics_collector

class PipelineProcessor:
    """Coordinates LLM-based entity extraction and formatting."""

    def __init__(self):
        self.llm_client = MultiLLMClient()

    async def process_content(self, source_name: str, category: str, content: str) -> List[Dict[str, Any]]:
        """
        Generates system instructions for the requested entity category,
        calls the LLM orchestrator, and parses the extracted entity results.
        Uses SHA-256 content hashing to cache and retrieve past LLM extractions.
        """
        logger.info(f"Processing content via LLM | Source: {source_name} | Category: {category}")
        
        # Calculate SHA-256 hash of the normalized content
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        
        # Check cache repository
        cache_repo = ContentCacheRepository()
        try:
            cached_extraction = cache_repo.get_cached(content_hash)
            if cached_extraction is not None:
                logger.info(f"LLM extraction cache hit for {source_name} (hash: {content_hash})")
                metrics_collector.increment("llm_cache_hits")
                entities = cached_extraction.get("entities", [])
                results = []
                for item in entities:
                    if isinstance(item, dict):
                        results.append({
                            "recordType": category,
                            "content": item
                        })
                return results
        except Exception as cache_err:
            logger.warning(f"Failed to fetch from LLM cache: {cache_err}")

        # Cache miss: increment metrics and run LLM
        metrics_collector.increment("llm_cache_misses")
        metrics_collector.increment("llm_calls")

        system_instruction = self._get_system_instruction(category)
        prompt = f"Crawled source content from '{source_name}':\n\n{content}\n\nExtract all entities of type '{category}'."

        try:
            raw_json = await self.llm_client.generate_json(prompt, system_instruction)
            parsed_data = json.loads(raw_json)
            
            # The LLM is requested to output a JSON object with key "entities" holding a list
            entities = parsed_data.get("entities", [])
            if not isinstance(entities, list):
                logger.warning(f"LLM returned invalid format (expected list under 'entities' key): {raw_json[:200]}")
                return []
                
            # Cache the raw extracted entities list
            try:
                cache_repo.cache_extraction(content_hash, {"entities": entities})
                logger.info(f"Cached LLM extraction for {source_name} (hash: {content_hash})")
            except Exception as cache_err:
                logger.warning(f"Failed to cache LLM extraction: {cache_err}")

            # Inject recordType into each item
            results = []
            for item in entities:
                if isinstance(item, dict):
                    results.append({
                        "recordType": category,
                        "content": item
                    })
            
            logger.info(f"LLM Processor succeeded | Source: {source_name} | Extracted {len(results)} entities")
            return results
        except Exception as e:
            logger.error(f"Failed during LLM processing/parsing: {e}")
            return []

    def _get_system_instruction(self, category: str) -> str:
        """Constructs system instructions detailing the expected JSON output schema."""
        base_instruction = (
            "You are an expert AI data extraction assistant. Analyze the provided text and extract a list of entities. "
            "Respond ONLY with a JSON object containing a single key 'entities' whose value is a JSON array of objects. "
            "Do not include any markdown format blocks (like ```json) or explanation text outside the JSON payload. "
            "Ensure the extracted attributes follow these definitions strictly:\n\n"
        )
        
        if category == EntityRecordType.STARTUP.value:
            schema_details = (
                "Entity Category: STARTUP\n"
                "JSON format:\n"
                "{\n"
                "  \"entities\": [\n"
                "    {\n"
                "      \"entityName\": \"Company Name\" (string, required),\n"
                "      \"data\": {\n"
                "        \"employeeCount\": 150 (integer or null, optional)\n"
                "      }\n"
                "    }\n"
                "  ]\n"
                "}"
            )
        elif category == EntityRecordType.PRODUCT.value:
            schema_details = (
                "Entity Category: PRODUCT\n"
                "JSON format:\n"
                "{\n"
                "  \"entities\": [\n"
                "    {\n"
                "      \"startupName\": \"Publisher or Brand Name\" (string, required),\n"
                "      \"pricingModel\": \"FREE\" | \"FREEMIUM\" | \"PAID\" | \"ENTERPRISE\" (string, required)\n"
                "    }\n"
                "  ]\n"
                "}"
            )
        elif category == EntityRecordType.RESEARCH_PAPER.value:
            schema_details = (
                "Entity Category: RESEARCH_PAPER\n"
                "JSON format:\n"
                "{\n"
                "  \"entities\": [\n"
                "    {\n"
                "      \"title\": \"Paper Title\" (string, required),\n"
                "      \"authors\": [\"Author 1\", \"Author 2\"] (array of strings, required),\n"
                "      \"paper_url\": \"https://arxiv.org/abs/...\" (string, required),\n"
                "      \"github_url\": \"https://github.com/...\" (string or null, optional),\n"
                "      \"github_stars\": 120 (integer or null, optional),\n"
                "      \"published_date\": \"YYYY-MM-DDTHH:MM:SSZ\" (string in ISO 8601 format, required)\n"
                "    }\n"
                "  ]\n"
                "}"
            )
        elif category == EntityRecordType.JOB.value:
            schema_details = (
                "Entity Category: JOB\n"
                "JSON format:\n"
                "{\n"
                "  \"entities\": [\n"
                "    {\n"
                "      \"company\": \"Company Name\" (string, required),\n"
                "      \"date\": \"YYYY-MM-DDTHH:MM:SSZ\" (string in ISO 8601 format, required),\n"
                "      \"is_remote\": true (boolean, required),\n"
                "      \"role_family\": \"Engineering\" | \"Product\" | \"Sales\" etc. (string, required)\n"
                "    }\n"
                "  ]\n"
                "}"
            )
        elif category == EntityRecordType.NEWS.value:
            schema_details = (
                "Entity Category: NEWS\n"
                "JSON format:\n"
                "{\n"
                "  \"entities\": [\n"
                "    {\n"
                "      \"title\": \"Headline\" (string, required),\n"
                "      \"summary\": \"Brief article summary\" (string or null, optional),\n"
                "      \"published_date\": \"YYYY-MM-DDTHH:MM:SSZ\" (string in ISO 8601 format, required),\n"
                "      \"url\": \"https://example.com/news/...\" (string, required)\n"
                "    }\n"
                "  ]\n"
                "}"
            )
        else:
            schema_details = "{}"
            
        return base_instruction + schema_details
