# 🚀 Adaptive Intelligence Ingestion Pipeline (AIIP)

![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green)
![MongoDB](https://img.shields.io/badge/MongoDB-Database-brightgreen)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Status](https://img.shields.io/badge/Status-Stable-blue)

> **GraphOne** is the overall project repository. **Adaptive Intelligence Ingestion Pipeline (AIIP)** is its core backend ingestion engine.
>
> AIIP is a modular backend pipeline for ingesting, validating, resolving, and tracking structured intelligence from the AI ecosystem.

---

## 📌 Table of Contents
- [📊 Final Results](#-final-results)
- [🎯 Assignment Deliverables](#-assignment-deliverables)
- [📖 Overview](#-overview)
- [🏗️ System Architecture](#️-system-architecture)
- [🧠 Hybrid Extraction Engine](#-hybrid-extraction-engine)
- [📡 API Endpoints & Swagger](#-api-endpoints--swagger)
- [📁 Folder Structure](#-folder-structure)
- [⚡ Scalability & Performance](#-scalability--performance)
- [🛠️ Engineering Highlights](#️-engineering-highlights)
- [⚙️ Getting Started](#️-getting-started)
- [🌐 Live Deployment](#-live-deployment)
- [⚠️ Known Limitations](#️-known-limitations)
- [📄 License](#-license)

---

## 📊 Final Results

The pipeline successfully executed a full end-to-end extraction run yielding the following verified, deduplicated database records:

| Dataset | Records | Target | Status |
|:---|---:|:---:|:---:|
| **Startups** | **5,754** | 1000+ | ✅ Achieved |
| **Products** | **1,103** | 1000+ | ✅ Achieved |
| **Research Papers** | **1,097** | 1000+ | ✅ Achieved |
| **News** | **176** | 50+ | ✅ Achieved |
| **Jobs** | **149** | 50+ | ✅ Achieved |
| **Entity Mappings** | **7,122** | N/A (Generated During Entity Resolution) | ✅ Achieved |

---

## 🎯 Assignment Deliverables

| Requirement | Status | Description |
|:---|:---:|:---|
| **1000+ Startups** | ✅ Achieved | 5,754 startups ingested from YC Companies API |
| **1000+ Products** | ✅ Achieved | 1,103 products/repos ingested from GitHub API and Trending |
| **1000+ Research Papers** | ✅ Achieved | 1,097 papers ingested from arXiv queries |
| **AI News Monitoring** | ✅ Achieved | 176 articles ingested from TechCrunch, ZDNet, Wired, VB, HF, and Google |
| **AI Job Monitoring** | ✅ Achieved | 149 jobs ingested from YC Jobs, RemoteOK, WWR, and AIJobsBoard |
| **Entity Resolution** | ✅ Achieved | RapidFuzz fuzzy name normalization with pre-seeded startups |
| **Knowledge Delta Engine**| ✅ Achieved | Deterministic merges, priority precedence, and ChangeHistory logs |
| **MongoDB Storage** | ✅ Achieved | MongoDB Atlas connection and repositories configured |
| **CSV Export** | ✅ Achieved | 6 flattened CSVs exported to `outputs/` directory |
| **Excel Export** | ✅ Achieved | Multi-sheet workbook exported to `outputs/excel/AIIP_Output.xlsx` |
| **Google Sheets Export** | ✅ Achieved | Implemented but requires Google credentials and verification before production use |
| **REST API Endpoints** | ✅ Achieved | Read-only FastAPI dataset endpoints exposed on `/docs` |
| **Deployment** | ✅ Achieved | Deployed live on Render Web Services |

---

## 📖 Overview

The **Adaptive Intelligence Ingestion Pipeline (AIIP)** is a scalable data ingestion system designed to transform unstructured information from multiple AI-related sources into validated, structured, and versioned knowledge.

Unlike traditional scrapers, AIIP detects incremental knowledge changes using a **Knowledge Delta Engine**, updating only modified entities while maintaining historical change records.

The pipeline automatically collects information about **AI startups, products, research papers, jobs, and news**, processes it using a hybrid extraction strategy, resolves duplicate entities, tracks changes over time, and exposes the final dataset via **REST API**, **MongoDB**, **CSV**, **Excel**, and **Google Sheets**.

---

## 🏗️ System Architecture

Detailed architectural documentation is available in [architecture.md](architecture.md) and the full specification in [architecture.pdf](architecture.pdf).

```mermaid
graph TD
    Sources[Data Sources] --> Registry[Source Registry YAML]
    Registry --> Crawler[Async Crawler Engine]
    Crawler --> Normalizer[Content Normalizer]
    Normalizer --> Strategy[Strategy Selector]
    Strategy --> Rule[Rule-Based Parser]
    Strategy --> JSONLD[JSON-LD Parser]
    Strategy --> LLM[Multi-Tier LLM Processor]
    Rule --> Validation[Schema Validation]
    JSONLD --> Validation
    LLM --> Validation
    Validation --> GitHub[GitHub API Enricher]
    GitHub --> Resolution[Entity Resolution]
    Resolution --> Delta[Knowledge Delta Engine]
    Delta --> MongoDB[(MongoDB)]
    MongoDB --> CSV[CSV Exporters]
    MongoDB --> Excel[Excel Exporter]
    MongoDB --> GoogleSheets[Google Sheets Sync]
    MongoDB --> FastAPI[FastAPI REST API]
```

---

## 🧠 Hybrid Extraction Engine

The pipeline automatically selects the most suitable extraction strategy using a cascaded decision tree to maximize extraction quality and efficiency:

```text
API available?
      │
     Yes ──► API Parser ──► Done
      │
      No
      │
JSON-LD exists?
      │
     Yes ──► JSON-LD Parser ──► Done
      │
      No
      │
Rule Extraction?
      │
     Yes ──► Rule Parser ──► Done
      │
      No
      │
LLM Extraction ──► Multi-LLM Fallback ──► Done
```

---

## 📡 API Endpoints & Swagger

The FastAPI application (`src/api/app.py`) exposes interactive Swagger UI documentation at `/docs` with MongoDB-level query pagination (`limit`, `skip`) and case-insensitive regex field filtering:

### Operational Endpoints
- `GET /` — Service directory map
- `GET /health` — Service health check
- `GET /metrics` — Operational telemetry metrics

### Dataset Endpoints
- `GET /startups` — Paginated AI startups (`limit`, `skip`, `name`)
- `GET /products` — Paginated AI products (`limit`, `skip`, `startup`)
- `GET /research-papers` — Paginated research papers (`limit`, `skip`, `title`)
- `GET /jobs` — Paginated AI job postings (`limit`, `skip`, `company`)
- `GET /news` — Paginated AI news signals (`limit`, `skip`, `title`)
- `GET /entity-mappings` — Fuzzy entity resolution logs (`limit`, `skip`, `raw_name`)
- `GET /changes` — Audit change history logs (`limit`, `operation`, `entity_id`)

---

## 📁 Folder Structure

```text
├── docs/                # Architecture and system documentation resources
├── outputs/             # Exported CSVs and Excel workbooks
│   └── excel/           # AIIP_Output.xlsx final multi-sheet workbook
├── src/
│   ├── api/             # FastAPI application and endpoint routes (app.py)
│   ├── config/          # Source registry definitions (sources.yaml) & settings
│   ├── crawler/         # Async Playwright & HTTP crawlers + normalizer
│   ├── database/        # MongoDB repositories and models
│   ├── delta/           # Knowledge Delta Engine for incremental updates
│   ├── exporters/       # CSV, Excel, and Google Sheets exporters
│   ├── llm/             # Multi-tier LLM clients (Gemini, Groq, OpenRouter)
│   ├── metrics/         # Run-time operational metrics collector
│   ├── pipeline/        # Validators, chunking processor, strategy selectors
│   ├── resolution/      # RapidFuzz entity resolver
│   ├── utils/           # GitHub REST API client & helpers
│   └── main.py          # CLI entrypoint for testing and full runs
├── Procfile             # Render web service start command
├── render.yaml          # Render Blueprint infrastructure spec
├── runtime.txt          # Python runtime version
├── requirements.txt     # Python dependencies
└── README.md            # Project documentation
```

---

## ⚡ Scalability & Performance

The pipeline is architected to scale efficiently:
- **Asynchronous Crawling**: High-performance HTTP fetching using aiohttp with custom worker semaphore limits.
- **MongoDB Offset Pagination**: Pagination (`limit`, `skip`) executed directly on database cursors inside PyMongo.
- **SHA-256 Caching**: Checks content integrity before LLM invocation and GitHub API calls, skipping repetitive API costs.
- **GitHub API Enrichment**: Automated repository metadata enrichment (stars, forks, language, description) with persistent DB caching.

---

## 🛠️ Engineering Highlights

### Entity Resolution

Duplicate entity names are normalized to a single canonical form by `src/resolution/resolver.py`:

1. **Corporate suffix cleaning** — `clean_name()` strips trailing punctuation and removes common suffixes (`Inc.`, `Ltd.`, `LLC`, `Corp.`, `GmbH`, etc.) using a regex before comparison.
2. **Exact match** — The cleaned name is looked up (case-insensitive) against an in-memory registry pre-seeded with 50 prominent AI companies.
3. **Fuzzy match** — If no exact match is found, RapidFuzz `token_sort_ratio` is run against all registered canonical names. A score ≥ 85.0 triggers a match (e.g., `"HuggingFace"` → `"Hugging Face"`).
4. **New entity registration** — Names below the threshold are registered as new canonical entities for future de-duplication within the same run.

Every resolution is logged to the `EntityMapping` MongoDB collection with the raw name, canonical name, resolution method (`EXACT` / `FUZZY` / `NEW`), and similarity score.

### Retry & Backoff

All HTTP and Playwright crawls share the same retry policy configured per source in `sources.yaml`:

- **Exponential backoff**: `delay = backoff_seconds × 2^attempt + jitter(0.1–1.0 s)`
  - Example: `backoff_seconds=5`, attempt 0 → ~5 s, attempt 1 → ~10 s, attempt 2 → ~20 s.
- **Rate-limiting**: Inter-request delay calculated as `60 / rate_limit_per_minute` seconds, randomised ±50% (±10% for paginated batches) to avoid strict pattern detection.
- **Configurable**: `max_retries` and `backoff_seconds` are per-source fields in `sources.yaml`. Exhausted retries log the final error and return a failed result without crashing the pipeline.

### Data Quality Safeguards

Multiple layers of data quality enforcement are applied before persistence:

- **Pydantic schema validation**: Every extracted record must satisfy its schema (`StartupEntity`, `JobEntity`, etc.). Required string fields enforce `min_length=1`; numeric fields enforce `ge=0`; missing required fields raise a `ValidationError` and discard the record.
- **URL format enforcement**: Source URLs and content URLs (e.g., `paper_url`, `NewsContent.url`) must start with `http://` or `https://`. A `sanitize_url()` helper prepends `https://` for bare domain strings; non-HTTP schemes are rejected with a logged error.
- **Job artifact filter**: Company names matching a known list of UI artifacts (e.g., `"See more jobs ›"`, `"Post a job"`, `"YC Startup"`) are discarded post-validation with a warning log identifying the rejected value.
- **LLM chunk deduplication**: Entities extracted across overlapping content chunks are deduplicated using category-specific keys (title for news, `paper_url` for papers, `company|role` for jobs) before the merged list is cached.
- **Delta Engine SKIP**: Records with an unchanged entity fingerprint are not re-written to MongoDB; the operation is logged as `SKIP` and counted in `duplicates_resolved` metrics.
- **Content normalisation**: Raw HTML is stripped of scripts, styles, and boilerplate by `ContentNormalizer` before being passed to any extractor, reducing noise in both rule-based and LLM extraction paths.

### Token Efficiency

The pipeline avoids unnecessary LLM invocations through two mechanisms:

- **SHA-256 content caching**: A SHA-256 hash of the normalised page content is checked against the `ContentCache` MongoDB collection before invoking the LLM. Cache hits return stored results immediately, skipping the API call entirely.
- **HTML stripping before LLM**: Page content is normalised and stripped of markup before being sent to the LLM, reducing the token count per request compared to raw HTML.
- **Context-window chunking**: Pages exceeding 3,500 characters are split into overlapping chunks (3-line overlap) to fit within model token limits, rather than truncating or dropping content.

### Validation Metrics

The pipeline emits a structured metrics summary at the end of every run (via `GET /metrics` or the end-of-run log):

| Metric | Description |
|:---|:---|
| `records_crawled` | Total records returned by all extractors before validation |
| `records_validated` | Records that passed Pydantic schema validation |
| `records_rejected` | Records discarded by validation (missing fields, bad URLs, job artifacts) |
| `duplicates_resolved` | Records skipped by the Delta Engine due to unchanged fingerprint |
| `records_exported` | Final row counts per entity category written to CSV / Excel |

---

## ⚙️ Getting Started

### 1. Clone the Repository
```bash
git clone https://github.com/Jishnu-Thakker-27/GraphOne.git
cd GraphOne
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
pip install playwright
playwright install chromium
```

### 3. Configure Environment Variables
Create a `.env` file in the root directory:
```env
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key
OPENROUTER_API_KEY=your_openrouter_key
MONGODB_URI=mongodb://localhost:27017/
```

### 4. Run the Pipeline & API Server
```bash
# Run full ingestion pipeline and exports
python -m src.main --all

# Start local FastAPI web server
uvicorn src.api.app:app --reload
```

---

## 🌐 Live Deployment

The application is deployed live on Render:

- **API**: https://aiip-api.onrender.com
- **Swagger**: https://aiip-api.onrender.com/docs
- **Health**: https://aiip-api.onrender.com/health

---

## ⚠️ Known Limitations

- **Google Sheets Live Sync**: Implemented but requires Google credentials and verification before production use.
- **Scheduling**: Pipeline runs via CLI trigger (`python -m src.main --all`); external scheduling (e.g. Render Cron Jobs or APScheduler) is recommended for continuous background automated runs.

---

## 📄 License

This project is released under the **MIT License**.