"""
Pipeline schemas and entity models.

Defines the canonical data contracts, common base models, custom field validators,
and internal DTOs (Data Transfer Objects) for all pipeline entities.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from src.utils.date_normalizer import DateNormalizer

# =========================================================================
# Enums
# =========================================================================

class PricingModel(str, Enum):
    FREE = "FREE"
    FREEMIUM = "FREEMIUM"
    PAID = "PAID"
    ENTERPRISE = "ENTERPRISE"

class EntityRecordType(str, Enum):
    STARTUP = "STARTUP"
    PRODUCT = "PRODUCT"
    RESEARCH_PAPER = "RESEARCH_PAPER"
    JOB = "JOB"
    NEWS = "NEWS"

class ExtractionStrategy(str, Enum):
    JSON_API = "JSON_API"
    JSON_LD = "JSON_LD"
    RULE_BASED = "RULE_BASED"
    LLM = "LLM"

# =========================================================================
# Common Helper Functions for Sanitization
# =========================================================================

def sanitize_string(v: Any) -> Any:
    """Helper to trim whitespace and standardize spacing for strings."""
    if isinstance(v, str):
        return " ".join(v.strip().split())
    return v

def sanitize_url(v: Any) -> Any:
    """Helper to ensure URL has a schema, prepending https:// if missing."""
    if isinstance(v, str):
        v_clean = v.strip()
        if not v_clean:
            return v_clean
        import re
        if re.match(r"^[a-zA-Z0-9+-.]+://", v_clean):
            return v_clean
        # If it's a path or domain-like string
        if "." in v_clean or "/" in v_clean:
            v_clean = "https://" + v_clean
        return v_clean
    return v

def sanitize_date(v: Any) -> Any:
    """Helper to normalize dates to timezone-aware UTC datetime."""
    if isinstance(v, str):
        return DateNormalizer.normalize(v)
    elif isinstance(v, datetime):
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)
    return v

# =========================================================================
# Common Helper Models
# =========================================================================

class SourceInfo(BaseModel):
    name: str = Field(..., min_length=1)
    url: str

    @model_validator(mode="before")
    @classmethod
    def clean_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "name" in data:
                data["name"] = sanitize_string(data["name"])
            if "url" in data:
                data["url"] = sanitize_url(data["url"])
        return data

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Ensure standard HTTP or HTTPS format for source URLs."""
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

class BaseEntity(BaseModel):
    schemaVersion: str = Field("1.0")
    recordType: EntityRecordType
    collectedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    observedAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
    entity_fingerprint: Optional[str] = None
    content_hash: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def clean_base_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Normalize collectedAt, observedAt, updatedAt if present
            for date_field in ["collectedAt", "observedAt", "updatedAt"]:
                if data.get(date_field):
                    data[date_field] = sanitize_date(data[date_field])
        return data

# =========================================================================
# Entity Schemas
# =========================================================================

class StartupData(BaseModel):
    employeeCount: Optional[int] = Field(None, ge=0)

class StartupContent(BaseModel):
    entityName: str = Field(..., min_length=1)
    data: StartupData = Field(default_factory=StartupData)

    @model_validator(mode="before")
    @classmethod
    def clean_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "entityName" in data:
                data["entityName"] = sanitize_string(data["entityName"])
        return data

class StartupEntity(BaseEntity):
    recordType: EntityRecordType = Field(EntityRecordType.STARTUP)
    source: SourceInfo
    content: StartupContent


class ProductContent(BaseModel):
    startupName: str = Field(..., min_length=1)
    pricingModel: PricingModel
    github_url: Optional[str] = None
    github_stars: Optional[int] = Field(None, ge=0)
    github_forks: Optional[int] = Field(None, ge=0)
    github_language: Optional[str] = None
    github_description: Optional[str] = None
    github_updated_at: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def clean_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "startupName" in data:
                data["startupName"] = sanitize_string(data["startupName"])
            if "pricingModel" in data and isinstance(data["pricingModel"], str):
                # Auto-normalize enum to uppercase
                data["pricingModel"] = data["pricingModel"].upper()
            if "github_url" in data:
                data["github_url"] = sanitize_url(data["github_url"])
            if "github_language" in data:
                data["github_language"] = sanitize_string(data["github_language"])
            if "github_description" in data:
                data["github_description"] = sanitize_string(data["github_description"])
            if "github_updated_at" in data:
                data["github_updated_at"] = sanitize_string(data["github_updated_at"])
        return data

class ProductEntity(BaseEntity):
    recordType: EntityRecordType = Field(EntityRecordType.PRODUCT)
    source: SourceInfo
    content: ProductContent


class ResearchPaperContent(BaseModel):
    title: str = Field(..., min_length=1)
    authors: List[str] = Field(default_factory=list)
    paper_url: str
    github_url: Optional[str] = None
    github_stars: Optional[int] = Field(None, ge=0)
    github_forks: Optional[int] = Field(None, ge=0)
    github_language: Optional[str] = None
    github_description: Optional[str] = None
    github_updated_at: Optional[str] = None
    published_date: Optional[datetime] = None # Optional now, never fabricate

    @model_validator(mode="before")
    @classmethod
    def clean_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "title" in data:
                data["title"] = sanitize_string(data["title"])
            if "authors" in data and isinstance(data["authors"], list):
                data["authors"] = [sanitize_string(a) for a in data["authors"]]
            if "paper_url" in data:
                data["paper_url"] = sanitize_url(data["paper_url"])
            if "github_url" in data:
                data["github_url"] = sanitize_url(data["github_url"])
            if "published_date" in data:
                data["published_date"] = sanitize_date(data["published_date"])
            if "github_language" in data:
                data["github_language"] = sanitize_string(data["github_language"])
            if "github_description" in data:
                data["github_description"] = sanitize_string(data["github_description"])
            if "github_updated_at" in data:
                data["github_updated_at"] = sanitize_string(data["github_updated_at"])
        return data

    @field_validator("paper_url", "github_url")
    @classmethod
    def validate_urls(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

class ResearchPaperEntity(BaseEntity):
    recordType: EntityRecordType = Field(EntityRecordType.RESEARCH_PAPER)
    source: SourceInfo
    content: ResearchPaperContent


class JobContent(BaseModel):
    company: str = Field(..., min_length=1)
    date: Optional[datetime] = None # Optional now
    is_remote: bool
    role_family: str = Field(..., min_length=1)

    @model_validator(mode="before")
    @classmethod
    def clean_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "company" in data:
                data["company"] = sanitize_string(data["company"])
            if "role_family" in data:
                data["role_family"] = sanitize_string(data["role_family"])
            if "date" in data:
                data["date"] = sanitize_date(data["date"])
        return data

class JobEntity(BaseEntity):
    recordType: EntityRecordType = Field(EntityRecordType.JOB)
    source: SourceInfo
    content: JobContent


class NewsContent(BaseModel):
    title: str = Field(..., min_length=1)
    summary: Optional[str] = None
    published_date: Optional[datetime] = None # Optional now
    url: str

    @model_validator(mode="before")
    @classmethod
    def clean_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "title" in data:
                data["title"] = sanitize_string(data["title"])
            if "summary" in data:
                data["summary"] = sanitize_string(data["summary"])
            if "url" in data:
                data["url"] = sanitize_url(data["url"])
            if "published_date" in data:
                data["published_date"] = sanitize_date(data["published_date"])
        return data

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

class NewsEntity(BaseEntity):
    recordType: EntityRecordType = Field(EntityRecordType.NEWS)
    source: SourceInfo
    content: NewsContent

# =========================================================================
# Support & Metadata Schemas
# =========================================================================

class ChangeHistory(BaseModel):
    entity_id: str = Field(..., min_length=1)
    entity_type: str = Field(..., min_length=1)
    operation: str = Field(..., min_length=1)  # INSERT, UPDATE, MERGE, SKIP
    changed_fields: list[str] = Field(default_factory=list)
    old_values: dict[str, Any] = Field(default_factory=dict)
    new_values: dict[str, Any] = Field(default_factory=dict)
    source: str = Field(..., min_length=1)
    source_priority: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    observed_at: datetime
    updated_at: datetime
    change_reason: str = Field(..., min_length=1)


class EntityMapping(BaseModel):
    rawName: str = Field(..., min_length=1)
    canonicalName: str = Field(..., min_length=1)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ContentCache(BaseModel):
    content_hash: str = Field(..., min_length=64, max_length=64)
    extraction: Dict[str, Any]
    cached_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# =========================================================================
# Pipeline DTOs (Data Transfer Objects)
# =========================================================================

class RawCrawlResult(BaseModel):
    source: str = Field(..., min_length=1)
    url: str
    status: int
    content: str
    timestamp: datetime
    retrieval_method: str

    @model_validator(mode="before")
    @classmethod
    def clean_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "url" in data:
                data["url"] = sanitize_url(data["url"])
            if "timestamp" in data:
                data["timestamp"] = sanitize_date(data["timestamp"])
        return data

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

class NormalizedContent(BaseModel):
    source: str = Field(..., min_length=1)
    url: str
    raw_content: str
    normalized_content: str
    timestamp: datetime
    retrieval_method: str

    @model_validator(mode="before")
    @classmethod
    def clean_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "url" in data:
                data["url"] = sanitize_url(data["url"])
            if "timestamp" in data:
                data["timestamp"] = sanitize_date(data["timestamp"])
        return data
