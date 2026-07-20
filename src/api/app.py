"""
FastAPI application for AIIP.

Exposes operational telemetry metrics, audit logs, and read-only dataset endpoints.
"""

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from src.config.config import settings
from src.metrics.collector import metrics_collector
from src.database.repositories import (
    StartupRepository,
    ProductRepository,
    ResearchPaperRepository,
    JobRepository,
    NewsRepository,
    EntityMappingRepository,
    ChangeHistoryRepository,
)

app = FastAPI(
    title="Adaptive Intelligence Ingestion Pipeline (AIIP) API",
    description="Programmatically exposes pipeline operational metrics, audit change history, read-only dataset collections, and direct Excel workbook downloads.",
    version="1.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def clean_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Helper to convert BSON ObjectId and datetimes for clean JSON serialization."""
    if not doc:
        return doc
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


def _get_google_sheets_url() -> Optional[str]:
    """Helper to retrieve configured non-placeholder Google Sheets URL."""
    url = settings.GOOGLE_SHEETS_URL
    if not url and settings.GOOGLE_SHEET_ID:
        url = f"https://docs.google.com/spreadsheets/d/{settings.GOOGLE_SHEET_ID}/edit"
    if url and "1AbCdEfGhIjKlMnOpQrStUvWxYz" not in url:
        return url
    return None


def _has_excel_workbook() -> bool:
    """Helper to check if Excel workbook output exists on disk."""
    p1 = os.path.join("outputs", "excel", "AIIP_Output.xlsx")
    p2 = os.path.join("outputs", "extracted_data.xlsx")
    return os.path.exists(p1) or os.path.exists(p2)


@app.get("/", tags=["Operational"], summary="API Root", description="Welcomes users and returns interactive API endpoints directory.")
def read_root():
    """Root endpoint welcoming users and directing them to OpenAPI documentation."""
    response = {
        "message": "Welcome to the Adaptive Intelligence Ingestion Pipeline (AIIP) API!",
        "docs_url": "/docs",
        "health_url": "/health",
        "metrics_url": "/metrics"
    }
    sheets_url = _get_google_sheets_url()
    if sheets_url:
        response["google_sheets_url"] = sheets_url
    if _has_excel_workbook():
        response["download_excel"] = "/download/excel"
    return response


@app.get(
    "/dataset",
    tags=["Datasets"],
    summary="Dataset Directory & Links",
    description="Returns links to the downloadable Excel dataset (if available) and Google Sheets dataset."
)
def get_dataset():
    """Returns dataset download links and public Google Sheets URL."""
    response = {
        "documentation": "/docs"
    }
    if _has_excel_workbook():
        response["excel_dataset"] = "/download/excel"
    sheets_url = _get_google_sheets_url()
    if sheets_url:
        response["google_sheets_url"] = sheets_url
    return response


@app.get(
    "/download/excel",
    tags=["Datasets"],
    summary="Download Excel Workbook",
    description="Returns the generated multi-sheet AIIP_Output.xlsx Excel workbook containing all 6 datasets."
)
def download_excel():
    """Serves the generated Excel workbook AIIP_Output.xlsx as a file download."""
    excel_path = os.path.join("outputs", "excel", "AIIP_Output.xlsx")
    if not os.path.exists(excel_path):
        excel_path = os.path.join("outputs", "extracted_data.xlsx")
    
    if not os.path.exists(excel_path):
        raise HTTPException(
            status_code=404,
            detail="Excel workbook not found. Please run the ingestion pipeline to generate outputs."
        )
    
    return FileResponse(
        path=excel_path,
        filename="AIIP_Output.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.get("/health", tags=["Operational"], summary="Service Health Check", description="Returns the operational health status and current timestamp.")
def health_check():
    """Returns the health status of the API service."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/metrics", tags=["Operational"], summary="Pipeline Telemetry Metrics", description="Returns collected run-time telemetry metrics including crawled counts, validation rates, and cache performance.")
def get_metrics():
    """
    Returns all collected pipeline operational metrics.
    Exposes metrics like crawled count, validation rates, API calls, cache performance, and processing time.
    """
    return metrics_collector.get_metrics()


@app.get("/startups", tags=["Datasets"], summary="Get AI Startups", description="Retrieves paginated AI startup records from MongoDB with optional name filtering.")
def get_startups(
    limit: int = Query(50, ge=1, le=500, description="Max records to return (default 50, max 500)"),
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination (default 0)"),
    name: Optional[str] = Query(None, description="Filter by Entity Name (case-insensitive search)")
):
    """Retrieves paginated startup records from MongoDB."""
    try:
        repo = StartupRepository()
    except Exception:
        raise HTTPException(status_code=404, detail="Repository unavailable")

    try:
        query = {}
        if name:
            query["content.entityName"] = {"$regex": name, "$options": "i"}
        docs = repo.find(query=query, limit=limit, skip=skip)
        return [clean_doc(d) for d in docs]
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error while fetching startups")


@app.get("/products", tags=["Datasets"], summary="Get AI Products", description="Retrieves paginated AI product and developer repository records from MongoDB.")
def get_products(
    limit: int = Query(50, ge=1, le=500, description="Max records to return (default 50, max 500)"),
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination (default 0)"),
    startup: Optional[str] = Query(None, description="Filter by Developer / Organization / Startup Name")
):
    """Retrieves paginated product records from MongoDB."""
    try:
        repo = ProductRepository()
    except Exception:
        raise HTTPException(status_code=404, detail="Repository unavailable")

    try:
        query = {}
        if startup:
            query["content.startupName"] = {"$regex": startup, "$options": "i"}
        docs = repo.find(query=query, limit=limit, skip=skip)
        return [clean_doc(d) for d in docs]
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error while fetching products")


@app.get("/research-papers", tags=["Datasets"], summary="Get AI Research Papers", description="Retrieves paginated research paper records from MongoDB with optional title filtering.")
def get_research_papers(
    limit: int = Query(50, ge=1, le=500, description="Max records to return (default 50, max 500)"),
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination (default 0)"),
    title: Optional[str] = Query(None, description="Filter by paper title (case-insensitive search)")
):
    """Retrieves paginated research paper records from MongoDB."""
    try:
        repo = ResearchPaperRepository()
    except Exception:
        raise HTTPException(status_code=404, detail="Repository unavailable")

    try:
        query = {}
        if title:
            query["content.title"] = {"$regex": title, "$options": "i"}
        docs = repo.find(query=query, limit=limit, skip=skip)
        return [clean_doc(d) for d in docs]
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error while fetching research papers")


@app.get("/jobs", tags=["Datasets"], summary="Get AI Job Postings", description="Retrieves paginated AI job postings from MongoDB with optional company filtering.")
def get_jobs(
    limit: int = Query(50, ge=1, le=500, description="Max records to return (default 50, max 500)"),
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination (default 0)"),
    company: Optional[str] = Query(None, description="Filter by Hiring Company (case-insensitive search)")
):
    """Retrieves paginated job posting records from MongoDB."""
    try:
        repo = JobRepository()
    except Exception:
        raise HTTPException(status_code=404, detail="Repository unavailable")

    try:
        query = {}
        if company:
            query["content.company"] = {"$regex": company, "$options": "i"}
        docs = repo.find(query=query, limit=limit, skip=skip)
        return [clean_doc(d) for d in docs]
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error while fetching jobs")


@app.get("/news", tags=["Datasets"], summary="Get AI News Signals", description="Retrieves paginated news signals from MongoDB with optional title filtering.")
def get_news(
    limit: int = Query(50, ge=1, le=500, description="Max records to return (default 50, max 500)"),
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination (default 0)"),
    title: Optional[str] = Query(None, description="Filter by News Article Title (case-insensitive search)")
):
    """Retrieves paginated news signal records from MongoDB."""
    try:
        repo = NewsRepository()
    except Exception:
        raise HTTPException(status_code=404, detail="Repository unavailable")

    try:
        query = {}
        if title:
            query["content.title"] = {"$regex": title, "$options": "i"}
        docs = repo.find(query=query, limit=limit, skip=skip)
        return [clean_doc(d) for d in docs]
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error while fetching news")


@app.get("/entity-mappings", tags=["Entity Resolution"], summary="Get Entity Name Mappings", description="Retrieves canonical name resolution mapping logs from MongoDB.")
def get_entity_mappings(
    limit: int = Query(50, ge=1, le=500, description="Max records to return (default 50, max 500)"),
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination (default 0)"),
    raw_name: Optional[str] = Query(None, description="Filter by Raw Entity Name (case-insensitive search)")
):
    """Retrieves paginated entity resolution mappings from MongoDB."""
    try:
        repo = EntityMappingRepository()
    except Exception:
        raise HTTPException(status_code=404, detail="Repository unavailable")

    try:
        query = {}
        if raw_name:
            query["rawName"] = {"$regex": raw_name, "$options": "i"}
        docs = repo.find(query=query, limit=limit, skip=skip)
        return [clean_doc(d) for d in docs]
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error while fetching entity mappings")


@app.get("/changes", tags=["Audit & History"], summary="Get Audit Change Logs", description="Returns audit change logs from the Knowledge Delta Engine.")
def get_changes(
    entity_id: Optional[str] = Query(None, description="Filter by Entity ID/Name"),
    operation: Optional[str] = Query(None, description="Filter by Operation (e.g. INSERT, MERGE)"),
    limit: int = Query(50, ge=1, le=100, description="Max logs to return (default 50, max 100)")
):
    """Returns the collection of audit change logs from the ChangeHistory repository."""
    try:
        repo = ChangeHistoryRepository()
    except Exception:
        raise HTTPException(status_code=404, detail="Repository unavailable")

    try:
        query = {}
        if entity_id:
            query["entity_id"] = entity_id
        if operation:
            query["operation"] = operation

        logs = repo.find(query=query)
        try:
            logs.sort(key=lambda x: x.get("timestamp") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        except Exception:
            pass

        return [clean_doc(l) for l in logs[:limit]]
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error while fetching audit logs")
