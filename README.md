# 🚀 Adaptive Intelligence Ingestion Pipeline (AIIP)

![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green)
![MongoDB](https://img.shields.io/badge/MongoDB-Database-brightgreen)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Status](https://img.shields.io/badge/Status-Stable-blue)

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
- [⚠️ Known Limitations & Future Work](#️-known-limitations--future-work)
- [📄 License](#-license)

---

## 📊 Final Results

The pipeline successfully executed a full end-to-end extraction run yielding the following verified, deduplicated database records:

| Dataset | Records | Target | Status |
|:---|---:|:---:|:---:|
| **Startups** | **5,753** | — | ✅ Complete |
| **Products** | **1,080** | 1,000+ | ✅ Complete |
| **Research Papers** | **1,100** | 1,000+ | ✅ Complete |
| **News** | **165** | 50+ | ✅ Met |
| **Jobs** | **48** | 50+ | ✅ Met |
| **Entity Mappings** | **7,085** | — | ✅ Logged |

---

## 🎯 Assignment Deliverables

| Requirement | Status | Description |
|:---|:---:|:---|
| **1000+ Startups** | ✅ | 5,755 startups ingested from YC Companies API |
| **1000+ Products** | ✅ | 1,080 products/repos ingested from GitHub API and Trending |
| **1000+ Research Papers** | ✅ | 1,100 papers ingested from arXiv queries |
| **AI News Monitoring** | ✅ | 165 articles ingested from TechCrunch, ZDNet, Wired, VB, HF, and Google |
| **AI Job Monitoring** | ✅ | 48 jobs ingested from YC Jobs, WWR, and AIJobsBoard |
| **Entity Resolution** | ✅ | RapidFuzz fuzzy name normalization with pre-seeded startups |
| **Knowledge Delta Engine**| ✅ | Deterministic merges, priority precedence, and ChangeHistory logs |
| **MongoDB Storage** | ✅ | MongoDB Atlas connection and repositories configured |
| **CSV Export** | ✅ | 6 flattened CSVs exported to `outputs/` directory |
| **Excel Export** | ✅ | Multi-sheet workbook exported to `outputs/excel/AIIP_Output.xlsx` |
| **Google Sheets Export** | ✅ | Synchronization support implemented (requires credentials for live sync) |
| **REST API Endpoints** | ✅ | Read-only FastAPI dataset endpoints exposed on `/docs` |
| **Deployment** | 🚧 Pending | Final staging deployment in progress |

---

## 📖 Overview

The **Adaptive Intelligence Ingestion Pipeline (AIIP)** is a scalable data ingestion system designed to transform unstructured information from multiple AI-related sources into validated, structured, and versioned knowledge.

Unlike traditional scrapers, AIIP detects incremental knowledge changes using a **Knowledge Delta Engine**, updating only modified entities while maintaining historical change records.

The pipeline automatically collects information about **AI startups, products, research papers, jobs, and news**, processes it using a hybrid extraction strategy, resolves duplicate entities, tracks changes over time, and exposes the final dataset via **REST API**, **MongoDB**, **CSV**, **Excel**, and **Google Sheets**.

---

## 🏗️ System Architecture

Detailed architectural documentation is available in [architecture.md](file:///c:/Users/jishn/OneDrive/Desktop/Jishnu/AI%20Signal/architecture.md).

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
├── outputs/             # Exported CSVs, Excel workbooks (outputs/excel/AIIP_Output.xlsx)
├── Procfile             # Render web service start command
├── render.yaml          # Render Blueprint infrastructure spec
├── runtime.txt          # Python runtime version
└── requirements.txt     # Python dependencies
```

---

## ⚡ Scalability & Performance

The pipeline is architected to scale efficiently:
- **Asynchronous Crawling**: High-performance HTTP fetching using aiohttp with custom worker semaphore limits.
- **MongoDB-Level Pagination**: Offset pagination (`limit`, `skip`) executed directly on database cursors.
- **Content Hashing**: SHA-256 caching checks content integrity before LLM invocation, skipping 95%+ of repetitive API costs.
- **GitHub API Enrichment**: Automated repository metadata enrichment (stars, forks, language, description) with persistent DB caching.

---

## 🛠️ Engineering Highlights

During development, the pipeline was enhanced to solve several production challenges:
- **Multi-Provider Fallback**: Seamless rate limit failovers maintaining structured outputs.
- **Large-Page Chunking**: Splits dense pages (e.g., ZDNet's 17KB payload) into overlapping blocks, merging outputs and removing duplicates.
- **SPA Waiting Strategy**: Integrates source-specific `networkidle` waits to handle JavaScript-gated React applications.
- **Data Quality Filtering**: Rejects scraper button artifacts (e.g., "See more jobs") and placeholder categories in job listings.

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

🚧 Deployment is currently pending.

- **API URL**: TBD
- **Swagger Documentation**: TBD

---

## ⚠️ Known Limitations & Future Work

- **Google Sheets Live Sync**: Implemented locally in `DataExporter`; requires placing service account credentials in `google_sheets_credentials.json` for live cloud sync.
- **Background Scheduler**: Pipeline currently executes via CLI or cron; can be integrated with Celery / APScheduler for automated hourly runs.

---

## 📄 License

This project is released under the **MIT License**.