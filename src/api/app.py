"""
FastAPI application for AIIP.

Exposes metrics and health check endpoints.
"""

from datetime import datetime, timezone
from fastapi import FastAPI, Query
from src.metrics.collector import metrics_collector
from src.database.repositories import ChangeHistoryRepository

app = FastAPI(
    title="Adaptive Intelligence Ingestion Pipeline (AIIP) API",
    description="Programmatically exposes pipeline operational run-time metrics.",
    version="1.0"
)

@app.get("/metrics")
def get_metrics():
    """
    Returns all collected pipeline operational metrics.
    Exposes metrics like crawled count, validation rates, API calls, cache performance, and processing time.
    """
    return metrics_collector.get_metrics()

@app.get("/changes")
def get_changes(
    entity_id: str | None = Query(None, description="Filter by Entity ID/Name"),
    operation: str | None = Query(None, description="Filter by Operation (e.g. INSERT, MERGE)"),
    limit: int = Query(50, ge=1, le=100, description="Max logs to return")
):
    """
    Returns the collection of audit change logs from the ChangeHistory repository.
    Supports optional filters for entity_id and operation type.
    """
    repo = ChangeHistoryRepository()
    query = {}
    if entity_id:
        query["entity_id"] = entity_id
    if operation:
        query["operation"] = operation
        
    logs = repo.find(query)
    try:
        # Sort logs by timestamp descending if available
        logs.sort(key=lambda x: x.get("timestamp") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    except Exception:
        pass
        
    return logs[:limit]

@app.get("/health")
def health_check():
    """Returns the health status of the API service."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
