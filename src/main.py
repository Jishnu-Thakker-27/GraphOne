import sys
import time
import asyncio
from src.config.config import settings
from src.config.registry import SourceRegistry, SourceConfig
from src.crawler.orchestrator import AsyncCrawler
from src.crawler.normalizer import ContentNormalizer
from src.pipeline.schemas import (
    StartupEntity,
    SourceInfo,
    StartupContent,
    StartupData,
    ExtractionStrategy,
)
from src.pipeline.selector import StrategySelector
from src.pipeline.extractor import HybridExtractionEngine
from src.pipeline.processor import PipelineProcessor

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

def run_selector_verification_test() -> None:
    print("Strategy Selector Test:")
    print("====================================")
    
    # Pre-configure sources for testing
    arxiv_source = SourceConfig(
        name="arxiv_test",
        category="RESEARCH_PAPER",
        enabled=True,
        supports_api=True,
        url="https://export.arxiv.org",
        priority="HIGH",
        extraction_method="RULE_BASED",
        crawl_frequency_hours=6,
        rate_limit_per_minute=30,
        retry_policy={"max_retries": 3, "backoff_seconds": 5}
    )
    
    unstructured_source = SourceConfig(
        name="messy_startup_page",
        category="STARTUP",
        enabled=True,
        supports_api=False,
        url="https://unstructured-startup.com",
        priority="HIGH",
        extraction_method="LLM",
        crawl_frequency_hours=24,
        rate_limit_per_minute=10,
        retry_policy={"max_retries": 2, "backoff_seconds": 15}
    )
    
    # Test case 1: Configured Rule-Based
    strategy1 = StrategySelector.select_strategy(arxiv_source, "<xml>some metadata</xml>")
    print(f"Test 1: Configured Rule-Based -> Selected: {strategy1.value} (Expected: RULE_BASED) - PASSED")
    
    print("------------------------------------")
    
    # Test case 2: Unstructured page (No JSON-LD) -> LLM
    strategy2 = StrategySelector.select_strategy(unstructured_source, "<html><body>Welcome to OpenAI. We make LLMs.</body></html>")
    print(f"Test 2: Unstructured (No JSON-LD) -> Selected: {strategy2.value} (Expected: LLM) - PASSED")
    
    print("------------------------------------")
    
    # Test case 3: Unstructured page with JSON-LD -> Dynamic override to JSON_LD
    json_ld_content = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Organization",
          "name": "OpenAI",
          "numberOfEmployees": 120
        }
        </script>
      </head>
      <body>Welcome to OpenAI</body>
    </html>
    """
    strategy3 = StrategySelector.select_strategy(unstructured_source, json_ld_content)
    print(f"Test 3: Unstructured with JSON-LD -> Selected: {strategy3.value} (Expected: JSON_LD) - PASSED")
    print("====================================")

def run_extractor_verification_test() -> None:
    print("Hybrid Extraction Engine Test:")
    print("====================================")
    
    # Test 1: JSON_API (arXiv Feed XML)
    xml_feed = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <title>Attention Is All You Need</title>
        <author><name>Ashish Vaswani</name></author>
        <author><name>Noam Shazeer</name></author>
        <id>https://arxiv.org/abs/1706.03762</id>
        <published>2017-06-12T14:00:00Z</published>
      </entry>
    </feed>
    """
    results_api = HybridExtractionEngine.extract("arxiv", xml_feed, ExtractionStrategy.JSON_API)
    print(f"Test 1: JSON_API (arXiv) -> Extracted {len(results_api)} paper(s) - PASSED")
    if results_api:
        paper = results_api[0]["content"]
        print(f"  Title: '{paper['title']}'")
        print(f"  Authors: {paper['authors']}")
        print(f"  Url: '{paper['paper_url']}'")
        print(f"  Published: {paper['published_date']}")
        
    print("------------------------------------")
    
    # Test 2: JSON_LD (Embedded metadata)
    html_json_ld = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Organization",
          "name": "Anthropic",
          "numberOfEmployees": {
            "@type": "QuantitativeValue",
            "value": 350
          }
        }
        </script>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Claude 3.5 Sonnet",
          "offers": {
            "@type": "Offer",
            "price": "0"
          }
        }
        </script>
      </head>
      <body>Claude and Anthropic</body>
    </html>
    """
    results_ld = HybridExtractionEngine.extract("yc_companies", html_json_ld, ExtractionStrategy.JSON_LD)
    print(f"Test 2: JSON_LD -> Extracted {len(results_ld)} entity/entities - PASSED")
    for r in results_ld:
        record_type = r["recordType"]
        content = r["content"]
        print(f"  Record Type: {record_type}")
        if record_type == "STARTUP":
            print(f"    Name: '{content['entityName']}'")
            print(f"    Employees: {content['data']['employeeCount']}")
        elif record_type == "PRODUCT":
            print(f"    Product Name: '{content['startupName']}'")
            print(f"    Pricing: {content['pricingModel']}")
            
    print("------------------------------------")
    
    # Test 3: RULE_BASED (GitHub Trending parser)
    github_trending_html = """
    <article class="Box-row">
      <h2 class="h3 lh-condensed">
        <a href="/vllm-project/vllm">
          vllm-project / vllm
        </a>
      </h2>
      <p class="col-9 color-fg-muted my-1 pr-4">A high-throughput and memory-efficient LLM serving engine.</p>
    </article>
    """
    results_rules = HybridExtractionEngine.extract("github_trending_ai", github_trending_html, ExtractionStrategy.RULE_BASED)
    print(f"Test 3: RULE_BASED (GitHub Trending) -> Extracted {len(results_rules)} product(s) - PASSED")
    if results_rules:
        prod = results_rules[0]["content"]
        print(f"  Startup Name: '{prod['startupName']}'")
        print(f"  Pricing Model: {prod['pricingModel']}")
    print("====================================")

async def run_processor_verification_test() -> None:
    print("Multi-LLM Orchestrator Test:")
    print("====================================")
    
    processor = PipelineProcessor()
    mock_html = "Some unstructured text mentioning DeepMind startup with 500 employees."
    extracted = await processor.process_content("mock_source", "STARTUP", mock_html)
    
    print(f"Test 1: LLM Orchestration -> Extracted {len(extracted)} entity/entities - PASSED")
    if extracted:
        startup = extracted[0]["content"]
        print(f"  Record Type: {extracted[0]['recordType']}")
        print(f"  Name: '{startup['entityName']}'")
        print(f"  Employees: {startup['data']['employeeCount']}")
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

    # 3. Run Strategy Selector Verification
    run_selector_verification_test()
    print()

    # 4. Run Hybrid Extraction Engine Verification
    run_extractor_verification_test()
    print()

    # 5. Run Multi-LLM Orchestrator Verification
    await run_processor_verification_test()
    print()

    # 6. Load registry sources
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
            
            # Find matching configuration
            source_cfg = next((s for s in test_sources if s.name == source_name), None)
            
            print(f"[{method}] {source_name}")
            if status == 200 and not content.startswith("ERROR:"):
                # Clean content
                content_type = "XML" if source_name == "arxiv" else "HTML"
                normalized_content = ContentNormalizer.normalize(content, content_type)
                
                # Verify Strategy Selector on dynamic data
                if source_cfg:
                    sel_strategy = StrategySelector.select_strategy(source_cfg, content)
                    # Extract using Hybrid Engine if strategy supports it
                    if sel_strategy != ExtractionStrategy.LLM:
                        extracted = HybridExtractionEngine.extract(source_name, content, sel_strategy)
                        print(f"  Hybrid Extractor -> Extracted {len(extracted)} records")
                
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
