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
                        self.browser = await self.playwright.chromium.launch(headless=True)

                    page = await self.browser.new_page()
                    try:
                        # Wait for 'domcontentloaded' instead of 'networkidle' to avoid timeouts on dynamic scripts
                        response = await page.goto(url, timeout=timeout_seconds * 1000, wait_until="domcontentloaded")
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
