import sys
import time
import asyncio
from src.config.config import settings
from src.config.registry import SourceRegistry
from src.crawler.orchestrator import AsyncCrawler

async def run_crawler_test() -> None:
    print("Adaptive Intelligence Ingestion Pipeline (AIIP) Initialized.\n")

    # 1. Validate environment configuration
    try:
        warnings = settings.validate()
        for warning in warnings:
            print(f"WARNING: {warning}")
    except ValueError as e:
        print(f"CRITICAL CONFIG ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. Load registry sources
    try:
        registry = SourceRegistry()
        enabled_sources = registry.load()
        print(f"Loaded {len(enabled_sources)} sources\n")
    except Exception as e:
        print(f"CRITICAL SOURCE REGISTRY ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Filter out one API source (arxiv) and one webpage source (github_trending_ai)
    api_source = next((s for s in enabled_sources if s.name == "arxiv"), None)
    web_source = next((s for s in enabled_sources if s.name == "github_trending_ai"), None)

    if not api_source or not web_source:
        print("CRITICAL ERROR: Example sources 'arxiv' and 'github_trending_ai' must be defined in sources.yaml", file=sys.stderr)
        sys.exit(1)

    test_sources = [api_source, web_source]

    print("Fetching:")
    print("====================================")
    
    start_total_time = time.time()
    
    async with AsyncCrawler(test_sources) as crawler:
        results = await crawler.crawl_all()
        
        attempted = len(results)
        successful = 0
        failed = 0
        
        for idx, result in enumerate(results):
            source_name = result["source"]
            method = result["retrieval_method"]
            status = result["status"]
            content = result["content"]
            
            print(f"[{method}] {source_name}")
            if status == 200 and not content.startswith("ERROR:"):
                size_kb = len(content.encode('utf-8')) / 1024
                print("SUCCESS")
                print(f"Received {size_kb:.0f} KB")
                successful += 1
            else:
                print("FAILED")
                print(f"Details: {content[:200]}")
                failed += 1
                
            if idx < len(results) - 1:
                print("------------------------------------")
                
    total_duration = time.time() - start_total_time
    print("====================================")
    
    print("\nCrawl Summary")
    print("-------------")
    print(f"Sources attempted : {attempted}")
    print(f"Successful        : {successful}")
    print(f"Failed            : {failed}")
    print(f"Total duration    : {total_duration:.2f}s")

def main() -> None:
    asyncio.run(run_crawler_test())

if __name__ == "__main__":
    main()
