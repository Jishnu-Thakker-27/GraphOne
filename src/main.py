import sys
import time
import asyncio
from src.config.config import settings
from src.config.registry import SourceRegistry
from src.crawler.orchestrator import AsyncCrawler
from src.crawler.normalizer import ContentNormalizer
from src.pipeline.schemas import (
    StartupEntity,
    SourceInfo,
    StartupContent,
    StartupData,
)

def run_schema_verification_test() -> None:
    print("Schema Validation Test:")
    print("====================================")
    
    # Test 1: Valid Startup Entity
    try:
        startup = StartupEntity(
            source=SourceInfo(name="yc_companies", url="https://www.ycombinator.com"),
            content=StartupContent(
                entityName="  OpenAI  ",  # standardizes spacing
                data=StartupData(employeeCount=120)
            )
        )
        print("Test 1: Valid Startup Entity creation - PASSED")
        print(f"  Normalized Entity Name: '{startup.content.entityName}'")
        print(f"  Employee Count: {startup.content.data.employeeCount}")
        print(f"  Record Type: {startup.recordType.value}")
        print(f"  Scraped At: {startup.collectedAt}")
    except Exception as e:
        print(f"Test 1: FAILED - {e}")
        
    print("------------------------------------")
    
    # Test 2: Invalid Startup Entity (Invalid URL format)
    try:
        StartupEntity(
            source=SourceInfo(name="yc_companies", url="ftp://invalid-url.com"),
            content=StartupContent(entityName="Invalid Company")
        )
        print("Test 2: Invalid URL - FAILED (expected validation error, but passed)")
    except Exception as e:
        print("Test 2: Invalid URL - PASSED (gracefully rejected invalid URL)")
        print(f"  Rejection Details: {str(e)[:150]}...")
        
    print("------------------------------------")

    # Test 3: Invalid Startup Entity (Negative Employee Count)
    try:
        StartupEntity(
            source=SourceInfo(name="yc_companies", url="https://www.ycombinator.com"),
            content=StartupContent(
                entityName="Negative Team",
                data=StartupData(employeeCount=-10)
            )
        )
        print("Test 3: Negative Employee Count - FAILED (expected validation error, but passed)")
    except Exception as e:
        print("Test 3: Negative Employee Count - PASSED (gracefully rejected negative value)")
        print(f"  Rejection Details: {str(e)[:150]}...")

    print("====================================")

async def run_pipeline_tests() -> None:
    print("Adaptive Intelligence Ingestion Pipeline (AIIP) Initialized.\n")

    # 1. Validate environment configuration
    try:
        warnings = settings.validate()
        for warning in warnings:
            print(f"WARNING: {warning}")
    except ValueError as e:
        print(f"CRITICAL CONFIG ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. Run Schema Verification
    run_schema_verification_test()
    print()

    # 3. Load registry sources
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

    print("Fetching & Normalizing:")
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
                # Clean content
                content_type = "XML" if source_name == "arxiv" else "HTML"
                normalized_content = ContentNormalizer.normalize(content, content_type)
                
                raw_size_kb = len(content.encode('utf-8')) / 1024
                norm_size_kb = len(normalized_content.encode('utf-8')) / 1024
                reduction = (1 - (norm_size_kb / raw_size_kb)) * 100 if raw_size_kb > 0 else 0
                
                print("SUCCESS")
                print(f"  Raw Payload Size: {raw_size_kb:.1f} KB")
                print(f"  Normalized Size : {norm_size_kb:.1f} KB (Reduced by {reduction:.1f}%)")
                
                # Print sample text
                sample = "\n".join(normalized_content.splitlines()[:4])
                print(f"  Sample Cleaned Text:\n  ---\n  {sample}\n  ---")
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
    asyncio.run(run_pipeline_tests())

if __name__ == "__main__":
    main()
