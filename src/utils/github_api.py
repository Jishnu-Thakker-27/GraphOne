"""
GitHub REST API Client.

Fetches repository metadata from the official GitHub API. Handles rate-limits,
database caching (24-hour expiration) with SHA-256 of repository URL as key,
and increments corresponding cache metrics.
"""

import os
import time
import hashlib
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
import aiohttp
from loguru import logger

from src.database.repositories import ContentCacheRepository
from src.metrics.collector import metrics_collector

class GitHubAPIClient:
    """Async client for interacting with the GitHub REST API with built-in rate-limiting and DB caching."""

    def __init__(self, session: Optional[aiohttp.ClientSession] = None) -> None:
        self.session = session
        self.token = os.getenv("GITHUB_TOKEN")
        self.rate_limit_reset: float = 0.0
        self.rate_limit_remaining: int = 60
        self.cache_repo = ContentCacheRepository()

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "AIIP-Client/1.0"
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    @staticmethod
    def parse_github_url(url: str) -> Optional[Tuple[str, str]]:
        """
        Extracts (owner, repo) from a GitHub URL.
        Example: https://github.com/vllm-project/vllm -> ("vllm-project", "vllm")
        """
        if not url:
            return None
        url = url.strip().rstrip("/")
        if "github.com/" not in url:
            return None
        try:
            parts = url.split("github.com/")[-1].split("/")
            if len(parts) >= 2:
                return parts[0], parts[1]
        except Exception as e:
            logger.debug(f"Failed to parse GitHub URL '{url}': {e}")
        return None

    async def fetch_repo_metadata(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """
        Fetches repository metadata from the GitHub REST API, checked against a 24-hour DB cache.
        Returns a dict containing stars, forks, language, description, and updated_at.
        """
        repo_url = f"https://github.com/{owner}/{repo}".lower()
        cache_key = hashlib.sha256(repo_url.encode("utf-8")).hexdigest()
        now_utc = datetime.now(timezone.utc)

        # 1. Check persistent cache in MongoDB
        try:
            cached_doc = self.cache_repo.find_one({"content_hash": cache_key})
            if cached_doc:
                cached_at = cached_doc.get("cached_at")
                if cached_at:
                    if isinstance(cached_at, str):
                        # Parse ISO string
                        cached_at = datetime.fromisoformat(cached_at.replace("Z", "+00:00"))
                    
                    # Convert cached_at to aware if naive
                    if cached_at.tzinfo is None:
                        cached_at = cached_at.replace(tzinfo=timezone.utc)
                    else:
                        cached_at = cached_at.astimezone(timezone.utc)

                    age = (now_utc - cached_at).total_seconds()
                    if age < 86400: # 24 hours
                        logger.info(f"GitHub API persistent cache hit for {owner}/{repo} (hash: {cache_key})")
                        metrics_collector.increment("github_cache_hits")
                        return cached_doc.get("extraction")
        except Exception as e:
            logger.warning(f"Error querying GitHub cache from database: {e}")

        # Cache miss
        metrics_collector.increment("github_cache_misses")

        # Rate limit check before calling API
        now_time = time.time()
        if self.rate_limit_remaining <= 0 and now_time < self.rate_limit_reset:
            wait_time = int(self.rate_limit_reset - now_time) + 1
            logger.warning(f"GitHub API rate limit exhausted. Resets in {wait_time}s. Skipping API fetch for {owner}/{repo}.")
            return None

        url = f"https://api.github.com/repos/{owner}/{repo}"
        logger.info(f"Calling GitHub API: {url}")

        local_session = self.session
        close_session = False
        if not local_session:
            local_session = aiohttp.ClientSession()
            close_session = True

        try:
            async with local_session.get(url, headers=self._get_headers(), timeout=10) as response:
                # Update local Rate Limit stats from response headers
                self.rate_limit_remaining = int(response.headers.get("X-RateLimit-Remaining", self.rate_limit_remaining))
                self.rate_limit_reset = float(response.headers.get("X-RateLimit-Reset", self.rate_limit_reset))

                if response.status == 200:
                    data = await response.json()
                    metadata = {
                        "stars": data.get("stargazers_count"),
                        "forks": data.get("forks_count"),
                        "language": data.get("language"),
                        "description": data.get("description"),
                        "updated_at": data.get("updated_at") # ISO 8601 string
                    }
                    
                    # Store in MongoDB cache
                    try:
                        self.cache_repo.update_one(
                            {"content_hash": cache_key},
                            {
                                "$set": {
                                    "content_hash": cache_key,
                                    "extraction": metadata,
                                    "cached_at": now_utc
                                }
                            },
                            upsert=True
                        )
                        logger.info(f"Cached GitHub API response for {owner}/{repo} (hash: {cache_key})")
                    except Exception as cache_err:
                        logger.warning(f"Failed to cache GitHub API response in DB: {cache_err}")

                    return metadata
                elif response.status == 404:
                    logger.warning(f"GitHub repository not found: {owner}/{repo}")
                    return None
                elif response.status == 403 or response.status == 429:
                    logger.warning(f"GitHub API rate limited (Status {response.status}) while fetching {owner}/{repo}")
                    return None
                else:
                    text = await response.text()
                    logger.warning(f"GitHub API returned status {response.status} for {owner}/{repo}: {text}")
                    return None
        except Exception as e:
            logger.error(f"Failed to fetch GitHub metadata for {owner}/{repo}: {e}")
            return None
        finally:
            if close_session:
                await local_session.close()
