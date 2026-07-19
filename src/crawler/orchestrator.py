"""
Async Crawler Orchestrator.

Retrieves raw content from configured sources concurrently.
Handles concurrency, retries with exponential backoff, rate limiting, and 
dynamic rendering fallback via Playwright.
"""

import asyncio
import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from loguru import logger
import aiohttp
from src.config.config import settings
from src.config.registry import SourceConfig

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

class AsyncCrawler:
    """Handles concurrent and rate-limited crawling of sources."""

    def __init__(self, sources: List[SourceConfig], max_concurrency: int = 5) -> None:
        self.sources = sources
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.session: Optional[aiohttp.ClientSession] = None
        self.playwright = None
        self.browser = None

    async def __aenter__(self):
        # Validate that Playwright is installed if any source requires it
        requires_playwright = any(not s.supports_api for s in self.sources)
        if requires_playwright and not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright library is not installed in the current environment.\n"
                "Please run:\n"
                "  pip install playwright\n"
                "  playwright install chromium"
            )

        # Initialize shared aiohttp session with standard browser headers
        self.session = aiohttp.ClientSession(headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.session:
                await self.session.close()
        except Exception as e:
            logger.warning(f"Error closing aiohttp session: {e}")

        try:
            if self.browser:
                await self.browser.close()
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")

        try:
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.warning(f"Error stopping playwright: {e}")

    async def crawl_all(self) -> List[Dict[str, Any]]:
        """Crawls all configured sources concurrently respecting concurrency limits."""
        tasks = [self.crawl_source_with_semaphore(source) for source in self.sources]
        return await asyncio.gather(*tasks)

    async def crawl_source_with_semaphore(self, source: SourceConfig) -> Dict[str, Any]:
        """Wraps crawl_source with a semaphore for concurrency control and applies rate limiting."""
        async with self.semaphore:
            # Calculate required rate limit delay based on source configuration
            delay = 60.0 / source.rate_limit_per_minute
            await asyncio.sleep(random.uniform(0.5 * delay, 1.5 * delay))
            return await self.crawl_source(source)

    async def crawl_source(self, source: SourceConfig) -> Dict[str, Any]:
        """Fetches raw content from a single source using either API or Playwright."""
        retrieval_method = "API" if source.supports_api else "PLAYWRIGHT"
        url = source.url
        max_retries = source.retry_policy.max_retries
        backoff_seconds = source.retry_policy.backoff_seconds
        timeout_seconds = settings.REQUEST_TIMEOUT

        logger.info(
            f"Crawl started | Source: {source.name} | Method: {retrieval_method} | "
            f"URL: {url} | Timeout: {timeout_seconds}s"
        )

        content = ""
        status = 0
        success = False
        start_time = time.time()

        # Check if the source has pagination enabled via research_target_count
        if source.research_target_count and source.supports_api:
            import urllib.parse as urlparse
            from urllib.parse import urlencode
            import xml.etree.ElementTree as ET
            import json

            target_count = source.research_target_count
            max_res_per_req = source.max_results_per_request or 50
            batch_size = source.batch_size or max_res_per_req
            
            logger.info(f"Initiating paginated crawling | Source: {source.name} | Target count: {target_count} | Batch size: {batch_size}")
            
            collected_data: List[Any] = []
            start_index = 0
            success = False
            status = 200
            
            # Base URL parsing
            url_parts = list(urlparse.urlparse(url))
            query = dict(urlparse.parse_qsl(url_parts[4]))
            query.pop("start", None)
            query.pop("max_results", None)
            query.pop("page", None)
            query.pop("per_page", None)
            
            start_time = time.time()
            
            while len(collected_data) < target_count:
                current_max = min(batch_size, target_count - len(collected_data))
                
                # Determine query params based on source type
                if source.name == "arxiv":
                    query["start"] = start_index
                    query["max_results"] = current_max
                else:
                    # GitHub-style page/per_page pagination (1-based page index)
                    query["page"] = (start_index // batch_size) + 1
                    query["per_page"] = current_max
                    
                url_parts[4] = urlencode(query)
                req_url = urlparse.urlunparse(url_parts)
                
                # Apply rate limiting before every paginated request after the first one
                if start_index > 0:
                    delay = 60.0 / source.rate_limit_per_minute
                    # Introduce subtle jitter to avoid strict pattern detection
                    await asyncio.sleep(random.uniform(0.9 * delay, 1.1 * delay))
                
                batch_content = ""
                batch_success = False
                
                for attempt in range(max_retries + 1):
                    try:
                        logger.info(f"Fetching batch: source={source.name}, start={start_index} (Attempt {attempt+1}/{max_retries+1})")
                        headers = {}
                        if "github.com" in req_url:
                            # Standard user agent header for GitHub API
                            headers = {"User-Agent": "AIIP-Ingestion-Pipeline-Agent"}
                        async with self.session.get(req_url, headers=headers, timeout=timeout_seconds) as response:
                            status = response.status
                            if status == 200:
                                batch_content = await response.text()
                                batch_success = True
                                break
                            else:
                                raise aiohttp.ClientResponseError(
                                    response.request_info,
                                    response.history,
                                    status=status,
                                    message=f"HTTP Error {status}"
                                )
                    except Exception as e:
                        if attempt < max_retries:
                            retry_delay = backoff_seconds * (2 ** attempt) + random.uniform(0.1, 1.0)
                            logger.warning(f"Batch fetch failed: {e}. Retrying in {retry_delay:.2f}s...")
                            await asyncio.sleep(retry_delay)
                        else:
                            logger.error(f"Batch fetch failed exhaustively at start={start_index}: {e}")
                            
                if not batch_success or not batch_content:
                    logger.warning("Failed to retrieve current batch. Stopping pagination loop to preserve partial results.")
                    break
                
                # Parse batch response based on content format
                if source.name == "arxiv":
                    try:
                        ATOM_NS = "http://www.w3.org/2005/Atom"
                        root = ET.fromstring(batch_content.encode("utf-8"))
                        entries = root.findall(f"{{{ATOM_NS}}}entry")
                        if not entries:
                            logger.info("No more research papers found in arXiv query feed. Stopping pagination.")
                            break
                        
                        collected_data.extend(entries)
                        success = True
                        logger.info(f"Collected {len(entries)} papers in batch. Total: {len(collected_data)}")
                        start_index += len(entries)
                    except Exception as parse_err:
                        logger.error(f"Failed to parse XML from arXiv batch: {parse_err}")
                        break
                else:
                    try:
                        res_json = json.loads(batch_content)
                        items = res_json.get("items", [])
                        if not items:
                            logger.info("No more products found in GitHub search results. Stopping pagination.")
                            break
                        
                        collected_data.extend(items)
                        success = True
                        logger.info(f"Collected {len(items)} products in batch. Total: {len(collected_data)}")
                        start_index += len(items)
                    except Exception as parse_err:
                        logger.error(f"Failed to parse JSON from GitHub products API: {parse_err}")
                        break
            
            # Serialize the combined elements back to a single payload
            if success and collected_data:
                status = 200
                if source.name == "arxiv":
                    entry_strs = [ET.tostring(entry, encoding="utf-8").decode("utf-8") for entry in collected_data]
                    content = f'<feed xmlns="http://www.w3.org/2005/Atom">\n' + "\n".join(entry_strs) + "\n</feed>"
                else:
                    content = json.dumps({"items": collected_data})
            else:
                content = "ERROR: No records were successfully crawled."
                status = 500
                success = False
                
            elapsed_time = time.time() - start_time
            logger.info(
                f"Crawl completed | Source: {source.name} | Success: {success} | "
                f"Status: {status} | Duration: {elapsed_time:.2f}s | Collected total: {len(collected_data)} records"
            )
            
            return {
                "source": source.name,
                "url": url,
                "status": status,
                "content": content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "retrieval_method": retrieval_method
            }

        for attempt in range(max_retries + 1):
            try:
                if retrieval_method == "API":
                    logger.info(f"Fetching {source.name} using API")
                    async with self.session.get(url, timeout=timeout_seconds) as response:
                        status = response.status
                        if status == 200:
                            content = await response.text()
                            success = True
                        else:
                            raise aiohttp.ClientResponseError(
                                response.request_info,
                                response.history,
                                status=status,
                                message=f"HTTP Error {status}"
                            )
                else:
                    logger.info(f"Fetching {source.name} using Playwright")
                    if not PLAYWRIGHT_AVAILABLE:
                        raise ImportError(
                            "Playwright is not installed. Run 'pip install playwright' and 'playwright install chromium'."
                        )

                    if not self.playwright:
                        self.playwright = await async_playwright().start()
                    if not self.browser:
                        self.browser = await self.playwright.chromium.launch(
                            headless=True,
                            args=["--disable-http2"]
                        )

                    page = await self.browser.new_page()
                    try:
                        # Use per-source wait strategy: domcontentloaded (default/fast) or
                        # networkidle (for SPA sources that render content via JavaScript)
                        pw_wait = getattr(source, "playwright_wait", "domcontentloaded")
                        pw_timeout_ms = getattr(source, "playwright_timeout_seconds", timeout_seconds) * 1000
                        response = await page.goto(url, timeout=pw_timeout_ms, wait_until=pw_wait)
                        status = response.status if response else 200
                        if status == 200 or status is None:
                            content = await page.content()
                            status = 200
                            success = True
                        else:
                            raise Exception(f"Playwright page load failed with HTTP status {status}")
                    finally:
                        await page.close()

                elapsed_time = time.time() - start_time
                logger.info(
                    f"Crawl succeeded | Source: {source.name} | Method: {retrieval_method} | "
                    f"Status: {status} | Duration: {elapsed_time:.2f}s | Size: {len(content)/1024:.1f} KB"
                )
                break

            except Exception as e:
                status = status or 500
                elapsed_time = time.time() - start_time
                if attempt < max_retries:
                    retry_delay = backoff_seconds * (2 ** attempt) + random.uniform(0.1, 1.0)
                    logger.warning(
                        f"Crawl failed (Attempt {attempt + 1}/{max_retries + 1}) | "
                        f"Source: {source.name} | Error: {e} | Retrying in {retry_delay:.2f}s..."
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(
                        f"Crawl failed exhaustively | Source: {source.name} | Method: {retrieval_method} | "
                        f"URL: {url} | Status: {status} | Duration: {elapsed_time:.2f}s | Error: {e}"
                    )
                    content = f"ERROR: {e}"

        return {
            "source": source.name,
            "url": url,
            "status": status,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "retrieval_method": retrieval_method
        }
