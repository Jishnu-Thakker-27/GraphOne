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

# Maximum characters per LLM chunk.
# Groq llama-3.1-8b-instant has a ~6K token/request limit (~24K chars).
# We use 3500 chars to leave headroom for the system instruction and response.
_MAX_CHUNK_CHARS = 3500

class PipelineProcessor:
    """Coordinates LLM-based entity extraction and formatting."""

    def __init__(self):
        self.llm_client = MultiLLMClient()

    async def process_content(self, source_name: str, category: str, content: str) -> List[Dict[str, Any]]:
        """
        Generates system instructions for the requested entity category,
        calls the LLM orchestrator, and parses the extracted entity results.
        Uses SHA-256 content hashing to cache and retrieve past LLM extractions.

        For large content (> _MAX_CHUNK_CHARS), the text is split into overlapping
        chunks, each chunk is extracted independently, and results are merged with
        deduplication before being cached and returned.
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

        # Split large content into chunks to stay within LLM token limits.
        # Entities near chunk boundaries may appear in two adjacent chunks;
        # deduplication removes these after merging.
        chunks = self._chunk_content(content)
        if len(chunks) > 1:
            logger.info(f"Content chunked | Source: {source_name} | {len(content)} chars -> {len(chunks)} chunks")

        all_entities: List[Dict] = []
        seen_keys: set = set()

        for chunk_idx, chunk in enumerate(chunks):
            chunk_label = f"{source_name} (chunk {chunk_idx+1}/{len(chunks)})" if len(chunks) > 1 else source_name
            prompt = f"Crawled source content from '{source_name}':\n\n{chunk}\n\nExtract all entities of type '{category}'."
            
            try:
                raw_json = await self.llm_client.generate_json(prompt, system_instruction)
                parsed_data = json.loads(raw_json)
                
                entities = parsed_data.get("entities", [])
                if not isinstance(entities, list):
                    logger.warning(f"LLM returned invalid format for {chunk_label}: {raw_json[:200]}")
                    continue
                
                for item in entities:
                    if not isinstance(item, dict):
                        continue
                    # Deduplicate across chunks using a category-specific key
                    dedup_key = self._dedup_key(item, category)
                    if dedup_key and dedup_key in seen_keys:
                        continue
                    if dedup_key:
                        seen_keys.add(dedup_key)
                    all_entities.append(item)
                    
            except Exception as e:
                logger.error(f"Failed during LLM processing for {chunk_label}: {e}")
                continue

        # Cache the merged, deduplicated entity list
        try:
            cache_repo.cache_extraction(content_hash, {"entities": all_entities})
            logger.info(f"Cached LLM extraction for {source_name} (hash: {content_hash})")
        except Exception as cache_err:
            logger.warning(f"Failed to cache LLM extraction: {cache_err}")

        # Inject recordType into each item
        results = [
            {"recordType": category, "content": item}
            for item in all_entities
            if isinstance(item, dict)
        ]

        logger.info(f"LLM Processor succeeded | Source: {source_name} | Extracted {len(results)} entities")
        return results

    def _chunk_content(self, content: str) -> List[str]:
        """
        Split content into chunks of at most _MAX_CHUNK_CHARS characters,
        breaking only at paragraph/line boundaries. Adds a 3-line overlap
        between adjacent chunks to avoid cutting entities in half.
        Returns a list with a single element when no chunking is needed.
        """
        if len(content) <= _MAX_CHUNK_CHARS:
            return [content]

        lines = content.splitlines()
        chunks: List[str] = []
        current: List[str] = []
        current_len = 0
        overlap_lines = 3  # lines carried forward to next chunk for context

        for line in lines:
            line_len = len(line) + 1  # +1 for the newline separator
            if current_len + line_len > _MAX_CHUNK_CHARS and current:
                chunks.append("\n".join(current))
                # Keep the last `overlap_lines` lines as leading context for next chunk
                current = current[-overlap_lines:] if len(current) >= overlap_lines else current[:]
                current_len = sum(len(l) + 1 for l in current)
            current.append(line)
            current_len += line_len

        if current:
            chunks.append("\n".join(current))

        return chunks

    @staticmethod
    def _dedup_key(item: Dict, category: str) -> str | None:
        """Compute a normalised deduplication key for an extracted entity."""
        try:
            if category == EntityRecordType.NEWS.value:
                title = item.get("title", "")
                return title.lower().strip() if title else None
            elif category == EntityRecordType.JOB.value:
                company = item.get("company", "")
                role = item.get("role_family", "")
                return f"{company.lower().strip()}|{role.lower().strip()}" if company else None
            elif category == EntityRecordType.RESEARCH_PAPER.value:
                url = item.get("paper_url", "")
                return url.lower().strip() if url else None
        except Exception:
            pass
        return None

    def _get_system_instruction(self, category: str) -> str:
        """Constructs system instructions detailing the expected JSON output schema."""
        base_instruction = (
            "You are an expert AI data extraction assistant. Analyze the provided text and extract a list of entities. "
            "Extract ALL distinct entities available in the supplied content. Do not stop after the first entity. "
            "Return every valid entity visible in the supplied text. Never merge unrelated entities. Never hallucinate. "
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
                "      \"date\": \"YYYY-MM-DDTHH:MM:SSZ\" (string in ISO 8601 format, or null if not shown),\n"
                "      \"is_remote\": true (boolean, required — true if job is remote, false if not),\n"
                "      \"role_family\": \"Engineering\" | \"Product\" | \"Sales\" | \"Research\" | \"Design\" | \"Operations\" | \"Other\" (string, required)\n"
                "    }\n"
                "  ]\n"
                "}\n"
                "IMPORTANT: Extract EVERY job posting visible in the text. "
                "If a date is not shown, use null. Do not skip jobs because a date is missing."
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
                "      \"published_date\": \"YYYY-MM-DDTHH:MM:SSZ\" (string in ISO 8601 format, or null if not shown),\n"
                "      \"url\": \"https://example.com/news/...\" (string, required)\n"
                "    }\n"
                "  ]\n"
                "}\n"
                "IMPORTANT: Every news article must have a valid URL. If a URL is not directly visible in the text, "
                "construct a valid URL by slugifying the title and appending it to the source domain "
                "(e.g., https://techcrunch.com/slugified-title). Never output null or empty values for the url field."
            )
        else:
            schema_details = "{}"
            
        return base_instruction + schema_details
