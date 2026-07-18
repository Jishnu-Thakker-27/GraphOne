# 🚀 Adaptive Intelligence Ingestion Pipeline (AIIP)

> A modular, production-inspired backend pipeline that continuously collects, validates, enriches, and tracks structured intelligence from the AI ecosystem.

---

## 📖 Overview

The **Adaptive Intelligence Ingestion Pipeline (AIIP)** is a scalable data ingestion system designed to transform unstructured information from multiple AI-related sources into validated, structured, and versioned knowledge.

The pipeline automatically collects information about **AI startups, products, research papers, jobs, and news**, processes it using a hybrid extraction strategy, resolves duplicate entities, tracks changes over time, and exports the final dataset to **MongoDB** and **Google Sheets**.

Rather than simply scraping websites, AIIP focuses on maintaining a continuously evolving knowledge base by identifying what has actually changed between pipeline runs.

---

# ✨ Key Features

### 📡 Config-Driven Source Registry
- Centralized YAML configuration for all data sources
- Easily add or remove sources without modifying code
- Supports API-based and web-based data sources
- Configurable rate limits, priorities, and retry policies

---

### 🕸️ Intelligent Crawling
- High-performance asynchronous crawling using **aiohttp**
- JavaScript rendering through **Playwright**
- Automatic selection between APIs and browser automation
- Built-in retry mechanism with exponential backoff

---

### 🧠 Hybrid Extraction Engine
The pipeline automatically selects the most suitable extraction strategy.

Supported methods include:

- Rule-Based Extraction
- JSON-LD Parsing
- LLM-Assisted Extraction
- Multi-LLM Fallback Chain

LLM Priority:

```
Gemini
    ↓
Groq
    ↓
DeepSeek
```

---

### ⚡ LLM Response Caching

To reduce API usage and improve execution speed:

- Normalized content is hashed using SHA-256
- Previously processed content is retrieved from cache
- Duplicate LLM requests are avoided

---

### ✅ Schema Validation

Every extracted entity is validated using **Pydantic** before entering the database.

Validation ensures:

- Required fields exist
- Data types are correct
- Invalid records are rejected early

---

### 🔍 Entity Resolution

Different websites often refer to the same company using different names.

Example:

```
Open AI
OpenAI
OpenAI Inc.
OpenAI LLC
```

AIIP identifies these as the same canonical entity using **RapidFuzz** and alias mapping.

---

### 📈 Knowledge Delta Engine

Instead of rewriting the database every time the pipeline runs, AIIP detects only meaningful changes.

Workflow:

```
Incoming Record
        │
        ▼
Entity Resolution
        │
        ▼
Previous Database Snapshot
        │
        ▼
Field Comparison
        │
        ├── No Changes
        │
        ├── New Entity
        │
        └── Updated Entity
                    │
                    ▼
              Change History
                    │
                    ▼
             Update MongoDB
```

Each update stores:

- Changed fields
- Previous value
- New value
- Timestamp
- Confidence score

---

### 📊 Operational Metrics

The pipeline records execution statistics including:

- Sources crawled
- Records extracted
- Duplicate entities resolved
- Rule-based vs LLM extractions
- Knowledge updates
- Processing time
- Errors encountered

---

### 📤 Data Export

Processed data can be exported to:

- CSV
- Google Sheets

Separate datasets are maintained for:

- Startups
- Products
- Research Papers
- Jobs
- News
- Entity Mapping

---

# 🏗️ System Architecture

```
                Sources
                   │
                   ▼
        Source Registry (YAML)
                   │
                   ▼
          Async Crawler Engine
                   │
                   ▼
         Content Normalizer
                   │
                   ▼
         Strategy Selector
                   │
      ┌────────────┴────────────┐
      ▼                         ▼
Rule-Based Parser         LLM Extraction
      │                         │
      └────────────┬────────────┘
                   ▼
          Schema Validation
                   │
                   ▼
          Entity Resolution
                   │
                   ▼
      Knowledge Delta Engine
                   │
                   ▼
              MongoDB
                   │
         ┌─────────┴─────────┐
         ▼                   ▼
       CSV Export      Google Sheets
```

---

# 🛠️ Technology Stack

| Layer | Technology |
|---------|------------|
| Language | Python 3.12+ |
| Backend | FastAPI |
| Database | MongoDB |
| Crawling | aiohttp, Playwright |
| HTML Parsing | BeautifulSoup4, selectolax |
| Validation | Pydantic |
| Entity Resolution | RapidFuzz |
| AI Models | Gemini, Groq, DeepSeek |
| Logging | Loguru |
| Configuration | YAML |
| Export | Pandas, Google Sheets |

---

# 📁 Project Structure

```
AIIP/
│
├── docs/
│   └── ADR/
│
├── outputs/
│   ├── csv/
│   ├── logs/
│   └── reports/
│
└── src/
    ├── api/
    ├── config/
    ├── crawler/
    ├── pipeline/
    ├── llm/
    ├── resolution/
    ├── delta/
    ├── database/
    ├── metrics/
    ├── exporters/
    └── utils/
```

---

# ⚙️ Getting Started

## 1. Clone the Repository

```bash
git clone <repository-url>
cd AIIP
```

---

## 2. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 3. Configure Environment Variables

Copy the example file.

```bash
cp .env.example .env
```

Example:

```env
GEMINI_API_KEY=your_api_key

MONGODB_URI=mongodb://localhost:27017/
```

Optional:

```env
GROQ_API_KEY=

DEEPSEEK_API_KEY=
```

---

## 4. Start MongoDB

Run MongoDB locally or configure a MongoDB Atlas connection.

---

## 5. Run the Pipeline

```bash
python src/main.py
```

---

# 📂 Architecture Decisions

Major design decisions are documented in:

```
docs/ADR/
```

Including:

- MongoDB selection
- Knowledge Delta Engine
- Hybrid Extraction Strategy

---

# 📈 Roadmap

Current implementation progress is tracked in:

```
ROADMAP.md
```

Development tasks are managed using:

```
task.md
```

---

# 🔮 Future Improvements

Potential future enhancements include:

- Continuous scheduled crawling
- Dashboard for monitoring
- Distributed crawling workers
- Graph database integration
- Semantic search over collected knowledge

---

# 🤝 Contributing

Contributions, suggestions, and improvements are welcome.

Feel free to fork the project, open issues, or submit pull requests.

---

# 📄 License

This project is released under the **MIT License**.

---

## ⭐ Acknowledgements

Built as part of an AI engineering assignment to explore scalable data ingestion, knowledge evolution, and intelligent information extraction using modern Python technologies.