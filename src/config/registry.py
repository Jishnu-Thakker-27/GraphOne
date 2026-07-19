"""
Source Registry Manager.

Defines schemas, Enums, Pydantic models, and loaders for config-driven
crawler source definitions in YAML.
"""

from enum import Enum
from pathlib import Path
from pydantic import BaseModel, Field, field_validator
import yaml

class SourceCategory(str, Enum):
    RESEARCH_PAPER = "RESEARCH_PAPER"
    PRODUCT = "PRODUCT"
    STARTUP = "STARTUP"
    JOB = "JOB"
    NEWS = "NEWS"

class Priority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class ExtractionMethod(str, Enum):
    API = "API"
    RULE_BASED = "RULE_BASED"
    LLM = "LLM"

class RetryPolicy(BaseModel):
    max_retries: int = Field(..., ge=0)
    backoff_seconds: int = Field(..., gt=0)

class SourceConfig(BaseModel):
    name: str
    category: SourceCategory
    enabled: bool
    supports_api: bool
    url: str
    priority: Priority
    precedence: int = Field(50, ge=0, le=100)
    extraction_method: ExtractionMethod
    crawl_frequency_hours: int = Field(..., gt=0)
    rate_limit_per_minute: int = Field(..., gt=0)
    retry_policy: RetryPolicy

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate that the URL starts with http:// or https://."""
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

class SourceRegistry:
    """Manages parsing, validating, and retrieving sources from configuration."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        if config_path is None:
            # Default path relative to this file
            base_dir = Path(__file__).parent
            config_path = base_dir / "sources.yaml"
        self.config_path = Path(config_path)
        self.sources: list[SourceConfig] = []

    def load(self) -> list[SourceConfig]:
        """
        Loads and validates sources from the YAML configuration.
        Raises ValueError if configuration is invalid.
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Source configuration file not found at {self.config_path}")

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML format in sources config: {e}")

        raw_sources = data.get("sources", [])
        if not isinstance(raw_sources, list):
            raise ValueError("'sources' key must define a list in sources.yaml")

        loaded_sources = []
        for index, raw_source in enumerate(raw_sources):
            try:
                # Validate using Pydantic model
                source = SourceConfig(**raw_source)
                loaded_sources.append(source)
            except Exception as e:
                source_name = raw_source.get("name", f"Index {index}")
                raise ValueError(f"Validation failed for source '{source_name}': {e}")

        self.sources = loaded_sources
        return self.sources

    def get_enabled_sources(self) -> list[SourceConfig]:
        """Returns a list of enabled sources."""
        return [source for source in self.sources if source.enabled]
