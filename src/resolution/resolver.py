"""
Fuzzy Entity Resolution.

Resolves variations of entity names to a single canonical name using RapidFuzz
similarity score thresholds and a pre-seeded registry of prominent AI companies.
"""

import re
from typing import Dict, List, Tuple
from loguru import logger
from rapidfuzz import fuzz, process

class EntityResolver:
    """Resolves raw entity names to standardized canonical representations using fuzzy matching."""

    # Pre-seeded list of 50 prominent AI companies
    PRE_SEEDED_COMPANIES = [
        "OpenAI", "Anthropic", "Cohere", "Mistral AI", "Hugging Face",
        "Perplexity AI", "Midjourney", "Character.ai", "Runway", "ElevenLabs",
        "Jasper", "Synthesia", "Scale AI", "Stability AI", "Inflection AI",
        "Adept AI", "Writer", "Glean", "Harvey", "HeyGen",
        "Pika Labs", "Phind", "Poe", "Luma AI", "Krea AI",
        "Leonardo AI", "CoreWeave", "Lambda Labs", "Together AI", "Anyscale",
        "DeepL", "AssemblyAI", "Replicate", "Pinecone", "Weaviate",
        "Qdrant", "Milvus", "Chroma", "LangChain", "LlamaIndex",
        "Weights & Biases", "Comet ML", "Arize AI", "Arthur AI", "Defog AI",
        "Groq", "Cerebras", "SambaNova", "Graphcore", "D-ID"
    ]

    def __init__(self, threshold: float = 85.0):
        self.threshold = threshold
        # In-memory registry mapping lowercase name -> canonical representation
        self.registry: Dict[str, str] = {name.lower(): name for name in self.PRE_SEEDED_COMPANIES}

    def clean_name(self, name: str) -> str:
        """Removes corporate suffixes and noise to assist string comparison."""
        name = name.strip()
        # Remove trailing/leading punctuation
        name = re.sub(r"^[^\w]+|[^\w]+$", "", name)
        # Remove common corporate suffixes (case-insensitive)
        suffixes = r"\b(inc|ltd|llc|corp|co|corporation|incorporated|gmbh|sa|pvt)\b"
        name = re.sub(suffixes, "", name, flags=re.IGNORECASE)
        # Clean up duplicate internal whitespaces
        name = " ".join(name.split())
        return name

    def resolve(self, raw_name: str) -> Tuple[str, bool]:
        """
        Resolves a raw name to a canonical string.
        Returns a tuple: (canonical_name, was_matched).
        """
        cleaned_raw = self.clean_name(raw_name)
        if not cleaned_raw:
            return raw_name, False

        cleaned_raw_lower = cleaned_raw.lower()

        # 1. Exact match in lower-cased registry keys
        if cleaned_raw_lower in self.registry:
            canonical = self.registry[cleaned_raw_lower]
            logger.info(f"Exact match resolved: '{raw_name}' -> '{canonical}'")
            return canonical, True

        # 2. Fuzzy match against registered canonical names
        canonical_list = list(self.registry.values())
        if canonical_list:
            # Extract closest match using RapidFuzz token_sort_ratio
            match_result = process.extractOne(
                cleaned_raw, 
                canonical_list, 
                scorer=fuzz.token_sort_ratio
            )
            if match_result:
                matched_name, score, _ = match_result
                if score >= self.threshold:
                    logger.info(
                        f"Fuzzy match resolved: '{raw_name}' -> '{matched_name}' "
                        f"(Similarity Score: {score:.1f}% >= threshold {self.threshold}%)"
                    )
                    return matched_name, True

        # 3. No match found: Register as a new canonical entity
        new_canonical = cleaned_raw
        self.registry[new_canonical.lower()] = new_canonical
        logger.info(f"No match found. Registered new canonical entity: '{raw_name}' -> '{new_canonical}'")
        return new_canonical, False
