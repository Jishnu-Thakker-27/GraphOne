"""
Pipeline schemas and entity models.

Defines the canonical data contracts, common base models, custom field validators,
and internal DTOs (Data Transfer Objects) for all pipeline entities.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

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
# Common Helper Models
# =========================================================================

class SourceInfo(BaseModel):
    name: str = Field(..., min_length=1)
    url: str

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
    collectedAt: datetime = Field(default_factory=datetime.utcnow)

# =========================================================================
# Entity Schemas
# =========================================================================

class StartupData(BaseModel):
    employeeCount: Optional[int] = Field(None, ge=0)

class StartupContent(BaseModel):
    entityName: str = Field(..., min_length=1)
    data: StartupData = Field(default_factory=StartupData)

    @field_validator("entityName")
    @classmethod
    def normalize_entity_name(cls, v: str) -> str:
        """Strip leading/trailing spaces and keep spaces standardized."""
        return " ".join(v.strip().split())

class StartupEntity(BaseEntity):
    recordType: EntityRecordType = Field(EntityRecordType.STARTUP)
    source: SourceInfo
    content: StartupContent


class ProductContent(BaseModel):
    startupName: str = Field(..., min_length=1)
    pricingModel: PricingModel

    @field_validator("startupName")
    @classmethod
    def normalize_startup_name(cls, v: str) -> str:
        """Standardize spaces for startup names."""
        return " ".join(v.strip().split())

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
    published_date: datetime

    @field_validator("paper_url", "github_url")
    @classmethod
    def validate_urls(cls, v: Optional[str]) -> Optional[str]:
        """Validate URLs if present."""
        if v is None:
            return v
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    @field_validator("title")
    @classmethod
    def normalize_title(cls, v: str) -> str:
        """Normalize research title spacing."""
        return " ".join(v.strip().split())

class ResearchPaperEntity(BaseEntity):
    recordType: EntityRecordType = Field(EntityRecordType.RESEARCH_PAPER)
    source: SourceInfo
    content: ResearchPaperContent


class JobContent(BaseModel):
    company: str = Field(..., min_length=1)
    date: datetime
    is_remote: bool
    role_family: str = Field(..., min_length=1)

    @field_validator("company", "role_family")
    @classmethod
    def normalize_strings(cls, v: str) -> str:
        """Normalize spaces for text attributes."""
        return " ".join(v.strip().split())

class JobEntity(BaseEntity):
    recordType: EntityRecordType = Field(EntityRecordType.JOB)
    source: SourceInfo
    content: JobContent


class NewsContent(BaseModel):
    title: str = Field(..., min_length=1)
    summary: Optional[str] = None
    published_date: datetime
    url: str

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Ensure news url starts with HTTP/HTTPS."""
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    @field_validator("title")
    @classmethod
    def normalize_title(cls, v: str) -> str:
        """Standardize spaces for news titles."""
        return " ".join(v.strip().split())

class NewsEntity(BaseEntity):
    recordType: EntityRecordType = Field(EntityRecordType.NEWS)
    source: SourceInfo
    content: NewsContent

# =========================================================================
# Support & Metadata Schemas
# =========================================================================

class ChangeHistory(BaseModel):
    entityName: str = Field(..., min_length=1)
    recordType: EntityRecordType
    field: str = Field(..., min_length=1)
    oldValue: Any
    newValue: Any
    confidence: float = Field(..., ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class EntityMapping(BaseModel):
    rawName: str = Field(..., min_length=1)
    canonicalName: str = Field(..., min_length=1)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ContentCache(BaseModel):
    content_hash: str = Field(..., min_length=64, max_length=64)  # SHA-256 string
    extraction: Dict[str, Any]
    cached_at: datetime = Field(default_factory=datetime.utcnow)

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
